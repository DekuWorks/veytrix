// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {MultiHopSwap} from "../src/MultiHopSwap.sol";
import {MockRouterBase, MockSwapRouter} from "./mocks/Mocks.sol";
import {IMultiHopSwap, SwapSuite} from "./SwapSuite.sol";

/// @dev Original SwapRouter layout (deadline inside the structs).
contract MultiHopSwapTest is SwapSuite {
    function _deployRouter() internal override returns (MockRouterBase) {
        return new MockSwapRouter();
    }

    function _deployHelper(address router_, address weth_)
        internal
        override
        returns (IMultiHopSwap)
    {
        return IMultiHopSwap(address(new MultiHopSwap(router_, weth_)));
    }

    function test_deadlineIsForwardedToRouter() public {
        vm.prank(user);
        swap.swapExactInputSingle(
            address(tokenA), address(tokenB), FEE, AMOUNT, MIN_OUT, deadline
        );
        assertEq(MockSwapRouter(address(router)).lastDeadline(), deadline);

        vm.prank(user);
        swap.swapExactInputMultihop(
            _path2(address(tokenA), address(tokenB)),
            false,
            false,
            AMOUNT,
            MIN_OUT,
            deadline + 7
        );
        assertEq(MockSwapRouter(address(router)).lastDeadline(), deadline + 7);
    }
}
