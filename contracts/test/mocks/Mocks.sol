// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract MockERC20 is ERC20 {
    constructor(string memory name_) ERC20(name_, name_) {}

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract MockWETH is ERC20 {
    constructor() ERC20("Wrapped Ether", "WETH") {}

    function deposit() external payable {
        _mint(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external {
        _burn(msg.sender, amount);
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "WETH: ETH transfer failed");
    }
}

/// @dev Pays out `amountIn * RATE` of the output token from its own balance.
abstract contract MockRouterBase {
    error TooLittleReceived();
    error Expired();

    uint256 public constant RATE = 2;

    uint256 public allowanceSeen;
    address public lastRecipient;
    address public lastTokenIn;
    address public lastTokenOut;
    uint256 public lastDeadline;
    uint256 public calls;

    function _swap(
        address tokenIn,
        address tokenOut,
        address recipient,
        uint256 amountIn,
        uint256 amountOutMinimum
    ) internal returns (uint256 amountOut) {
        calls++;
        allowanceSeen = IERC20(tokenIn).allowance(msg.sender, address(this));
        lastRecipient = recipient;
        lastTokenIn = tokenIn;
        lastTokenOut = tokenOut;

        IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);
        amountOut = amountIn * RATE;
        if (amountOut < amountOutMinimum) revert TooLittleReceived();
        IERC20(tokenOut).transfer(recipient, amountOut);
    }

    function _first(bytes calldata path) internal pure returns (address) {
        return address(bytes20(path[0:20]));
    }

    function _last(bytes calldata path) internal pure returns (address) {
        return address(bytes20(path[path.length - 20:]));
    }
}

/// @dev Original SwapRouter struct layout (deadline inside the structs).
contract MockSwapRouter is MockRouterBase {
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

    function exactInputSingle(ExactInputSingleParams calldata p)
        external
        payable
        returns (uint256)
    {
        if (block.timestamp > p.deadline) revert Expired();
        lastDeadline = p.deadline;
        return _swap(
            p.tokenIn, p.tokenOut, p.recipient, p.amountIn, p.amountOutMinimum
        );
    }

    function exactInput(ExactInputParams calldata p)
        external
        payable
        returns (uint256)
    {
        if (block.timestamp > p.deadline) revert Expired();
        lastDeadline = p.deadline;
        return _swap(
            _first(p.path),
            _last(p.path),
            p.recipient,
            p.amountIn,
            p.amountOutMinimum
        );
    }
}

/// @dev SwapRouter02 (IV3SwapRouter) struct layout: no deadline field.
contract MockSwapRouter02 is MockRouterBase {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }

    struct ExactInputParams {
        bytes path;
        address recipient;
        uint256 amountIn;
        uint256 amountOutMinimum;
    }

    function exactInputSingle(ExactInputSingleParams calldata p)
        external
        payable
        returns (uint256)
    {
        return _swap(
            p.tokenIn, p.tokenOut, p.recipient, p.amountIn, p.amountOutMinimum
        );
    }

    function exactInput(ExactInputParams calldata p)
        external
        payable
        returns (uint256)
    {
        return _swap(
            _first(p.path),
            _last(p.path),
            p.recipient,
            p.amountIn,
            p.amountOutMinimum
        );
    }
}

/// @dev A caller that refuses ETH, to exercise EthTransferFailed.
contract EthRejecter {
    function approveAndSwap(
        address helper,
        address token,
        bytes calldata callData
    ) external returns (bool ok, bytes memory ret) {
        IERC20(token).approve(helper, type(uint256).max);
        (ok, ret) = helper.call(callData);
    }
}
