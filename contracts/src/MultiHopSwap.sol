// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from
    "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/// @notice Minimal Uniswap V3 SwapRouter surface used here.
/// @dev    Matches the original SwapRouter (deadline inside the structs).
///         SwapRouter02 has no `deadline` field, so its selectors differ and
///         every call against it would revert.
interface ISwapRouter {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }

    struct ExactInputParams {
        bytes path;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
    }

    function exactInputSingle(ExactInputSingleParams calldata params)
        external
        payable
        returns (uint256 amountOut);

    function exactInput(ExactInputParams calldata params)
        external
        payable
        returns (uint256 amountOut);
}

/// @notice Minimal WETH interface for wrapping/unwrapping native ETH.
interface IWETH9 is IERC20 {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

/// @title MultiHopSwap
/// @notice Non-custodial Uniswap V3 swap helper supporting single- and
///         multi-hop routes, plus native ETH in/out via WETH wrapping.
///         The contract never retains user funds or fees: everything is
///         pulled, swapped, and forwarded within a single transaction.
/// @dev    No owner, no admin, no pause, no rescue functions. There is
///         deliberately no privileged role that can move user assets.
///         Fee-on-transfer and rebasing tokens are not supported: the
///         router's pull of `amountIn` reverts when less arrives.
contract MultiHopSwap {
    using SafeERC20 for IERC20;

    /// @dev Set once at deploy time; can never change.
    ISwapRouter public immutable router;
    IWETH9 public immutable weth;

    /// @dev Sentinel used to mean "native ETH" in token arguments.
    address public constant NATIVE = address(0);

    uint256 private constant ADDR_SIZE = 20;
    uint256 private constant FEE_SIZE = 3;
    uint256 private constant HOP_SIZE = ADDR_SIZE + FEE_SIZE;
    uint256 private constant MIN_PATH_LENGTH = ADDR_SIZE + HOP_SIZE;

    error ZeroAmount();
    error ZeroMinOut();
    error DeadlineInPast();
    error InvalidPath();
    error WrongMsgValue();
    error EthTransferFailed();
    error NotWeth();

    event Swapped(
        address indexed user,
        address indexed tokenIn,
        address indexed tokenOut,
        uint256 amountIn,
        uint256 amountOut
    );

    constructor(address router_, address weth_) {
        if (router_ == address(0) || weth_ == address(0)) {
            revert InvalidPath();
        }
        router = ISwapRouter(router_);
        weth = IWETH9(weth_);
    }

    /// @notice Only WETH may send ETH here (during unwrap). This prevents
    ///         stray ETH from being trapped.
    receive() external payable {
        if (msg.sender != address(weth)) revert NotWeth();
    }

    /// @notice Swap an exact input amount through a single Uniswap V3 pool.
    /// @param tokenIn      Input token, or NATIVE to pay with ETH.
    /// @param tokenOut     Output token, or NATIVE to receive ETH.
    /// @param fee          Pool fee tier in hundredths of a bip (e.g. 3000).
    /// @param amountIn     Exact amount of input to spend.
    /// @param amountOutMin Minimum output; must be non-zero (slippage guard).
    /// @param deadline     Unix timestamp after which the swap reverts.
    /// @return amountOut   Amount of output delivered to the caller.
    function swapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline
    ) external payable returns (uint256 amountOut) {
        _validate(amountIn, amountOutMin, deadline);

        bool ethOut = tokenOut == NATIVE;
        address realTokenOut = ethOut ? address(weth) : tokenOut;
        address expectedTokenIn = tokenIn == NATIVE ? address(weth) : tokenIn;
        if (expectedTokenIn == realTokenOut) revert InvalidPath();

        address realTokenIn = _receiveInput(tokenIn, amountIn);
        address recipient = ethOut ? address(this) : msg.sender;

        IERC20(realTokenIn).forceApprove(address(router), amountIn);

        amountOut = router.exactInputSingle(
            ISwapRouter.ExactInputSingleParams({
                tokenIn: realTokenIn,
                tokenOut: realTokenOut,
                fee: fee,
                recipient: recipient,
                deadline: deadline,
                amountIn: amountIn,
                amountOutMinimum: amountOutMin,
                sqrtPriceLimitX96: 0
            })
        );

        IERC20(realTokenIn).forceApprove(address(router), 0);

        if (ethOut) _unwrapAndSend(amountOut);

        emit Swapped(msg.sender, tokenIn, tokenOut, amountIn, amountOut);
    }

    /// @notice Swap an exact input amount along a multi-pool Uniswap V3 path.
    /// @param path         Packed path: token (20) | fee (3) | token (20) ...
    /// @param ethIn        Pay with ETH; the path must start with WETH.
    /// @param ethOut       Receive ETH; the path must end with WETH.
    /// @param amountIn     Exact amount of input to spend.
    /// @param amountOutMin Minimum output; must be non-zero (slippage guard).
    /// @param deadline     Unix timestamp after which the swap reverts.
    /// @return amountOut   Amount of output delivered to the caller.
    function swapExactInputMultihop(
        bytes calldata path,
        bool ethIn,
        bool ethOut,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline
    ) external payable returns (uint256 amountOut) {
        _validate(amountIn, amountOutMin, deadline);
        _validatePath(path);

        address firstToken = _firstToken(path);
        address lastToken = _lastToken(path);

        if (ethIn && firstToken != address(weth)) revert InvalidPath();
        if (ethOut && lastToken != address(weth)) revert InvalidPath();

        address inputToken = ethIn ? NATIVE : firstToken;
        address outputToken = ethOut ? NATIVE : lastToken;

        address realTokenIn = _receiveInput(inputToken, amountIn);
        address recipient = ethOut ? address(this) : msg.sender;

        IERC20(realTokenIn).forceApprove(address(router), amountIn);

        amountOut = router.exactInput(
            ISwapRouter.ExactInputParams({
                path: path,
                recipient: recipient,
                deadline: deadline,
                amountIn: amountIn,
                amountOutMinimum: amountOutMin
            })
        );

        IERC20(realTokenIn).forceApprove(address(router), 0);

        if (ethOut) _unwrapAndSend(amountOut);

        emit Swapped(msg.sender, inputToken, outputToken, amountIn, amountOut);
    }

    /// @notice Build a packed Uniswap V3 path from tokens and fee tiers.
    /// @param tokens Ordered tokens, at least two.
    /// @param fees   Fee tiers, exactly `tokens.length - 1`.
    /// @return path  Packed path suitable for `swapExactInputMultihop`.
    function encodePath(address[] calldata tokens, uint24[] calldata fees)
        external
        pure
        returns (bytes memory path)
    {
        if (tokens.length < 2 || fees.length != tokens.length - 1) {
            revert InvalidPath();
        }

        path = abi.encodePacked(tokens[0]);
        for (uint256 i = 0; i < fees.length; ) {
            path = abi.encodePacked(path, fees[i], tokens[i + 1]);
            unchecked {
                ++i;
            }
        }
    }

    function _validate(uint256 amountIn, uint256 amountOutMin, uint256 deadline)
        private
        view
    {
        if (amountIn == 0) revert ZeroAmount();
        if (amountOutMin == 0) revert ZeroMinOut();
        if (deadline < block.timestamp) revert DeadlineInPast();
    }

    function _validatePath(bytes calldata path) private pure {
        if (
            path.length < MIN_PATH_LENGTH ||
            (path.length - ADDR_SIZE) % HOP_SIZE != 0
        ) revert InvalidPath();
    }

    function _receiveInput(address tokenIn, uint256 amountIn)
        private
        returns (address realTokenIn)
    {
        if (tokenIn == NATIVE) {
            if (msg.value != amountIn) revert WrongMsgValue();
            weth.deposit{value: amountIn}();
            return address(weth);
        }

        if (msg.value != 0) revert WrongMsgValue();
        IERC20(tokenIn).safeTransferFrom(
            msg.sender,
            address(this),
            amountIn
        );
        return tokenIn;
    }

    function _unwrapAndSend(uint256 amount) private {
        weth.withdraw(amount);
        (bool ok, ) = msg.sender.call{value: amount}("");
        if (!ok) revert EthTransferFailed();
    }

    function _firstToken(bytes calldata path)
        private
        pure
        returns (address token)
    {
        token = address(bytes20(path[0:ADDR_SIZE]));
    }

    function _lastToken(bytes calldata path)
        private
        pure
        returns (address token)
    {
        token = address(bytes20(path[path.length - ADDR_SIZE:]));
    }
}
