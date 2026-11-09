// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";

import {
    EthRejecter,
    MockERC20,
    MockRouterBase,
    MockWETH
} from "./mocks/Mocks.sol";

/// @dev External surface shared by MultiHopSwap and MultiHopSwap02.
interface IMultiHopSwap {
    error ZeroAmount();
    error ZeroMinOut();
    error DeadlineInPast();
    error InvalidPath();
    error WrongMsgValue();
    error EthTransferFailed();
    error NotWeth();

    function router() external view returns (address);
    function weth() external view returns (address);
    function NATIVE() external view returns (address);

    function swapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint24 fee,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline
    ) external payable returns (uint256);

    function swapExactInputMultihop(
        bytes calldata path,
        bool ethIn,
        bool ethOut,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline
    ) external payable returns (uint256);

    function encodePath(address[] calldata tokens, uint24[] calldata fees)
        external
        pure
        returns (bytes memory);
}

/// @dev Each variant's test contract supplies its router and helper.
abstract contract SwapSuite is Test {
    event Swapped(
        address indexed user,
        address indexed tokenIn,
        address indexed tokenOut,
        uint256 amountIn,
        uint256 amountOut
    );

    uint24 internal constant FEE = 3000;
    uint256 internal constant AMOUNT = 1 ether;
    uint256 internal constant MIN_OUT = 1;
    address internal constant NATIVE = address(0);

    IMultiHopSwap internal swap;
    MockRouterBase internal router;
    MockWETH internal weth;
    MockERC20 internal tokenA;
    MockERC20 internal tokenB;
    MockERC20 internal tokenC;
    address internal user = makeAddr("user");
    uint256 internal deadline;

    function _deployRouter() internal virtual returns (MockRouterBase);

    function _deployHelper(address router_, address weth_)
        internal
        virtual
        returns (IMultiHopSwap);

    function setUp() public virtual {
        vm.warp(1_800_000_000);
        deadline = block.timestamp + 120;

        weth = new MockWETH();
        tokenA = new MockERC20("A");
        tokenB = new MockERC20("B");
        tokenC = new MockERC20("C");
        router = _deployRouter();
        swap = _deployHelper(address(router), address(weth));

        // Router liquidity for every possible output token.
        tokenA.mint(address(router), 1_000 ether);
        tokenB.mint(address(router), 1_000 ether);
        tokenC.mint(address(router), 1_000 ether);
        vm.deal(address(this), 1_000 ether);
        weth.deposit{value: 1_000 ether}();
        weth.transfer(address(router), 1_000 ether);

        tokenA.mint(user, 100 ether);
        vm.deal(user, 100 ether);
        vm.prank(user);
        tokenA.approve(address(swap), type(uint256).max);
        vm.prank(user);
        weth.approve(address(swap), type(uint256).max);
    }

    // -- helpers ---------------------------------------------------------

    function _path2(address a, address b) internal pure returns (bytes memory) {
        return abi.encodePacked(a, FEE, b);
    }

    function _path3(address a, address b, address c)
        internal
        pure
        returns (bytes memory)
    {
        return abi.encodePacked(a, FEE, b, uint24(500), c);
    }

    function _assertNoResidue() internal view {
        assertEq(address(swap).balance, 0, "helper kept ETH");
        assertEq(weth.balanceOf(address(swap)), 0, "helper kept WETH");
        assertEq(tokenA.balanceOf(address(swap)), 0, "helper kept A");
        assertEq(tokenB.balanceOf(address(swap)), 0, "helper kept B");
        assertEq(tokenC.balanceOf(address(swap)), 0, "helper kept C");
        assertEq(tokenA.allowance(address(swap), address(router)), 0);
        assertEq(weth.allowance(address(swap), address(router)), 0);
    }

    // -- construction ----------------------------------------------------

    function test_constructorRejectsZeroAddresses() public {
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        _deployHelper(address(0), address(weth));
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        _deployHelper(address(router), address(0));
    }

    function test_immutablesAreSet() public view {
        assertEq(swap.router(), address(router));
        assertEq(swap.weth(), address(weth));
        assertEq(swap.NATIVE(), address(0));
    }

    // -- input validation ------------------------------------------------

    function test_zeroAmountReverts() public {
        vm.startPrank(user);
        vm.expectRevert(IMultiHopSwap.ZeroAmount.selector);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, 0, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.ZeroAmount.selector);
        swap.swapExactInputMultihop(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            0,
            MIN_OUT,
            deadline
        );
        vm.stopPrank();
    }

    function test_zeroMinOutReverts() public {
        vm.startPrank(user);
        vm.expectRevert(IMultiHopSwap.ZeroMinOut.selector);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, AMOUNT, 0, deadline
        );
        vm.expectRevert(IMultiHopSwap.ZeroMinOut.selector);
        swap.swapExactInputMultihop(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            AMOUNT,
            0,
            deadline
        );
        vm.stopPrank();
    }

    function test_pastDeadlineReverts() public {
        uint256 past = block.timestamp - 1;
        vm.startPrank(user);
        vm.expectRevert(IMultiHopSwap.DeadlineInPast.selector);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, AMOUNT, MIN_OUT, past
        );
        vm.expectRevert(IMultiHopSwap.DeadlineInPast.selector);
        swap.swapExactInputMultihop(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            past
        );
        vm.stopPrank();
    }

    function test_deadlineEqualToNowIsAccepted() public {
        vm.prank(user);
        swap.swapExactInputSingle(
            address(tokenA),
            address(tokenB),
            FEE,
            AMOUNT,
            MIN_OUT,
            block.timestamp
        );
    }

    function test_wrongMsgValueReverts() public {
        vm.startPrank(user);
        vm.expectRevert(IMultiHopSwap.WrongMsgValue.selector);
        swap.swapExactInputSingle{value: AMOUNT - 1}(
            NATIVE, address(tokenB), FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.WrongMsgValue.selector);
        swap.swapExactInputSingle{value: 1}(
            address(tokenA), address(tokenB), FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.WrongMsgValue.selector);
        swap.swapExactInputMultihop{value: AMOUNT + 1}(
            _path2(address(weth), address(tokenB)),
            true,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        vm.expectRevert(IMultiHopSwap.WrongMsgValue.selector);
        swap.swapExactInputMultihop{value: 1}(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        vm.stopPrank();
    }

    function test_sameTokenSingleHopReverts() public {
        vm.startPrank(user);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenA), FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputSingle{value: AMOUNT}(
            NATIVE, NATIVE, FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputSingle{value: AMOUNT}(
            NATIVE, address(weth), FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputSingle(
            address(weth), NATIVE, FEE, AMOUNT, MIN_OUT, deadline
        );
        vm.stopPrank();
    }

    function _expectInvalidLength(uint256 length) internal {
        bytes memory path = new bytes(length);
        vm.prank(user);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputMultihop(
            path, false, false, AMOUNT, MIN_OUT, deadline
        );
    }

    function test_invalidPathLengthsRevert() public {
        uint256[9] memory lengths = [
            uint256(0), 20, 23, 42, 44, 65, 67, 88, 90
        ];
        for (uint256 i = 0; i < lengths.length; i++) {
            _expectInvalidLength(lengths[i]);
        }
    }

    function test_validPathLengthsAreAccepted() public {
        vm.startPrank(user);
        swap.swapExactInputMultihop(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        bytes memory twoHop =
            _path3(address(tokenA), address(tokenB), address(tokenC));
        assertEq(twoHop.length, 66);
        swap.swapExactInputMultihop(
            twoHop, false, false, AMOUNT, MIN_OUT, deadline
        );
        vm.stopPrank();
    }

    function test_ethInPathMustStartWithWeth() public {
        vm.prank(user);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputMultihop{value: AMOUNT}(
            _path2(address(tokenA), address(weth)),
            true,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
    }

    function test_ethOutPathMustEndWithWeth() public {
        vm.prank(user);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.swapExactInputMultihop(
            _path3(address(tokenA), address(weth), address(tokenB)),
            false,
            true,
            AMOUNT,
            MIN_OUT,
            deadline
        );
    }

    function test_slippageRevertFromRouterBubbles() public {
        vm.prank(user);
        vm.expectRevert(MockRouterBase.TooLittleReceived.selector);
        swap.swapExactInputSingle(
            address(tokenA),
            address(tokenB),
            FEE,
            AMOUNT,
            AMOUNT * 2 + 1,
            deadline
        );
    }

    // -- happy paths -----------------------------------------------------

    function test_singleErc20ToErc20() public {
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, address(tokenA), address(tokenB), AMOUNT, AMOUNT * 2);
        vm.prank(user);
        uint256 out = swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, AMOUNT, MIN_OUT, deadline
        );

        assertEq(out, AMOUNT * 2);
        assertEq(tokenB.balanceOf(user), AMOUNT * 2);
        assertEq(router.lastRecipient(), user);
        assertEq(router.allowanceSeen(), AMOUNT);
        _assertNoResidue();
    }

    function test_singleNativeIn() public {
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, NATIVE, address(tokenB), AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputSingle{value: AMOUNT}(
            NATIVE, address(tokenB), FEE, AMOUNT, MIN_OUT, deadline
        );

        assertEq(router.lastTokenIn(), address(weth));
        assertEq(tokenB.balanceOf(user), AMOUNT * 2);
        assertEq(user.balance, 100 ether - AMOUNT);
        _assertNoResidue();
    }

    function test_singleNativeOutDeliversEth() public {
        uint256 before = user.balance;
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, address(tokenA), NATIVE, AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputSingle(
            address(tokenA), NATIVE, FEE, AMOUNT, MIN_OUT, deadline
        );

        assertEq(router.lastRecipient(), address(swap));
        assertEq(router.lastTokenOut(), address(weth));
        assertEq(user.balance, before + AMOUNT * 2);
        _assertNoResidue();
    }

    function test_multihopEventReportsEndsOfPath() public {
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, address(tokenA), address(tokenC), AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputMultihop(
            _path3(address(tokenA), address(tokenB), address(tokenC)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );

        assertEq(tokenC.balanceOf(user), AMOUNT * 2);
        assertEq(router.allowanceSeen(), AMOUNT);
        _assertNoResidue();
    }

    function test_multihopEthIn() public {
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, NATIVE, address(tokenC), AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputMultihop{value: AMOUNT}(
            _path3(address(weth), address(tokenB), address(tokenC)),
            true,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        assertEq(router.lastTokenIn(), address(weth));
        _assertNoResidue();
    }

    function test_multihopEthOutDeliversEth() public {
        uint256 before = user.balance;
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, address(tokenA), NATIVE, AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputMultihop(
            _path3(address(tokenA), address(tokenB), address(weth)),
            false,
            true,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        assertEq(user.balance, before + AMOUNT * 2);
        _assertNoResidue();
    }

    function test_wethAsErc20InputWithoutEthFlag() public {
        vm.prank(user);
        weth.deposit{value: AMOUNT}();
        vm.expectEmit(true, true, true, true, address(swap));
        emit Swapped(user, address(weth), address(tokenB), AMOUNT, AMOUNT * 2);
        vm.prank(user);
        swap.swapExactInputMultihop(
            _path2(address(weth), address(tokenB)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            deadline
        );
        _assertNoResidue();
    }

    // -- ETH handling ----------------------------------------------------

    function test_receiveRejectsNonWeth() public {
        vm.prank(user);
        (bool ok, bytes memory ret) = address(swap).call{value: 1}("");
        assertFalse(ok);
        assertEq(bytes4(ret), IMultiHopSwap.NotWeth.selector);
        assertEq(address(swap).balance, 0);
    }

    function test_ethOutToRejectingCallerReverts() public {
        EthRejecter rejecter = new EthRejecter();
        tokenA.mint(address(rejecter), AMOUNT);
        bytes memory callData = abi.encodeCall(
            IMultiHopSwap.swapExactInputSingle,
            (address(tokenA), NATIVE, FEE, AMOUNT, MIN_OUT, deadline)
        );
        (bool ok, bytes memory ret) =
            rejecter.approveAndSwap(address(swap), address(tokenA), callData);
        assertFalse(ok);
        assertEq(bytes4(ret), IMultiHopSwap.EthTransferFailed.selector);
        assertEq(tokenA.balanceOf(address(rejecter)), AMOUNT);
    }

    // -- encodePath ------------------------------------------------------

    function test_encodePathMatchesPackedEncoding() public view {
        address[] memory tokens = new address[](3);
        tokens[0] = address(tokenA);
        tokens[1] = address(tokenB);
        tokens[2] = address(tokenC);
        uint24[] memory fees = new uint24[](2);
        fees[0] = FEE;
        fees[1] = 500;

        bytes memory path = swap.encodePath(tokens, fees);
        assertEq(path, _path3(address(tokenA), address(tokenB), address(tokenC)));
        assertEq(path.length, 66);
    }

    function test_encodePathRejectsBadShapes() public {
        address[] memory one = new address[](1);
        uint24[] memory none = new uint24[](0);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.encodePath(one, none);

        address[] memory two = new address[](2);
        uint24[] memory twoFees = new uint24[](2);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.encodePath(two, twoFees);
        vm.expectRevert(IMultiHopSwap.InvalidPath.selector);
        swap.encodePath(two, none);
    }

    function testFuzz_singleSwapLeavesNoResidue(uint96 amount) public {
        vm.assume(amount > 0 && amount <= 100 ether);
        vm.prank(user);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, amount, MIN_OUT, deadline
        );
        _assertNoResidue();
    }
}
