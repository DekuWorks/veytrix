// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import {MultiHopSwap} from "../src/MultiHopSwap.sol";
import {MultiHopSwap02} from "../src/MultiHopSwap02.sol";

/// @dev Fork tests run against real Uniswap deployments in a LOCAL fork.
///      Nothing is broadcast. Each test skips unless its RPC env var is set:
///        SEPOLIA_RPC_URL=... forge test --match-contract Fork
///        MAINNET_RPC_URL=... forge test --match-contract Fork
///      Never hardcode an RPC URL here; provider URLs embed API keys.
///      Addresses: https://docs.uniswap.org/contracts/v3/reference/deployments/ethereum-deployments
///      and https://developers.circle.com/stablecoins/usdc-contract-addresses
contract SepoliaForkTest is Test {
    address constant ROUTER02 = 0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E;
    address constant WETH = 0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14;
    address constant USDC = 0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238;

    MultiHopSwap02 swap;
    address user = makeAddr("forkUser");

    function _fork() internal returns (bool) {
        string memory url = vm.envOr("SEPOLIA_RPC_URL", string(""));
        if (bytes(url).length == 0) return false;
        vm.createSelectFork(url);
        swap = new MultiHopSwap02(ROUTER02, WETH);
        vm.deal(user, 1 ether);
        return true;
    }

    function test_fork_ethToUsdcSingle() public {
        if (!_fork()) {
            vm.skip(true);
            return;
        }
        vm.prank(user);
        uint256 out = swap.swapExactInputSingle{value: 0.001 ether}(
            address(0), USDC, 3000, 0.001 ether, 1, block.timestamp + 120
        );
        assertGt(out, 0);
        assertEq(IERC20(USDC).balanceOf(user), out);
        assertEq(address(swap).balance, 0);
        assertEq(IERC20(WETH).balanceOf(address(swap)), 0);
    }
}

contract MainnetForkTest is Test {
    address constant ROUTER = 0xE592427A0AEce92De3Edee1F18E0157C05861564;
    address constant WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    address constant USDC = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;

    MultiHopSwap swap;
    address user = makeAddr("forkUser");

    function _fork() internal returns (bool) {
        string memory url = vm.envOr("MAINNET_RPC_URL", string(""));
        if (bytes(url).length == 0) return false;
        vm.createSelectFork(url);
        swap = new MultiHopSwap(ROUTER, WETH);
        vm.deal(user, 10 ether);
        return true;
    }

    function test_fork_ethToUsdcAndBack() public {
        if (!_fork()) {
            vm.skip(true);
            return;
        }
        uint256 deadline = block.timestamp + 120;

        vm.startPrank(user);
        uint256 usdc = swap.swapExactInputSingle{value: 1 ether}(
            address(0), USDC, 500, 1 ether, 1, deadline
        );
        assertGt(usdc, 0);

        IERC20(USDC).approve(address(swap), usdc);
        uint256 before = user.balance;
        uint256 eth = swap.swapExactInputMultihop(
            abi.encodePacked(USDC, uint24(500), WETH),
            false,
            true,
            usdc,
            1,
            deadline
        );
        vm.stopPrank();

        assertEq(user.balance, before + eth);
        assertEq(IERC20(USDC).allowance(address(swap), ROUTER), 0);
        assertEq(address(swap).balance, 0);
    }
}
