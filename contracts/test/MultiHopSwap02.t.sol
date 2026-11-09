// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {MultiHopSwap02} from "../src/MultiHopSwap02.sol";
import {MockRouterBase, MockSwapRouter02} from "./mocks/Mocks.sol";
import {IMultiHopSwap, SwapSuite} from "./SwapSuite.sol";

/// @dev SwapRouter02 layout (no deadline field). The suite's deadline tests
///      prove the helper's own check still applies.
contract MultiHopSwap02Test is SwapSuite {
    function _deployRouter() internal override returns (MockRouterBase) {
        return new MockSwapRouter02();
    }

    function _deployHelper(address router_, address weth_)
        internal
        override
        returns (IMultiHopSwap)
    {
        return IMultiHopSwap(address(new MultiHopSwap02(router_, weth_)));
    }

    function test_expiredDeadlineNeverReachesRouter() public {
        uint256 past = block.timestamp - 1;
        vm.prank(user);
        vm.expectRevert(IMultiHopSwap.DeadlineInPast.selector);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, AMOUNT, MIN_OUT, past
        );
        assertEq(router.calls(), 0);
    }
}
