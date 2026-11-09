// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console2} from "forge-std/Script.sol";

import {MultiHopSwap02} from "../src/MultiHopSwap02.sol";

/// @notice Deploys one helper variant. Testnet only in this build.
/// @dev    Dry run (simulation, sends nothing):
///           forge script script/Deploy.s.sol --rpc-url "$SWAPBOT_RPC_URL"
///         Real deploy needs `--broadcast` added by a human.
///
///         Env:
///           SWAPBOT_PRIVATE_KEY  dedicated testnet hot wallet (never printed)
///           SWAPBOT_VARIANT      "swaprouter02" (default) or "swaprouter"
///
///         Sepolia only lists SwapRouter02, so "swaprouter" (MultiHopSwap,
///         original router) is refused. It can only be added here once a
///         testnet with the original SwapRouter is verified from Uniswap docs.
///         Addresses: https://docs.uniswap.org/contracts/v3/reference/deployments/ethereum-deployments
contract Deploy is Script {
    uint256 internal constant SEPOLIA = 11155111;
    address internal constant SEPOLIA_ROUTER02 =
        0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E;
    address internal constant SEPOLIA_WETH =
        0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14;

    function run() external returns (address helper) {
        require(block.chainid == SEPOLIA, "Deploy: testnet only (Sepolia)");

        string memory variant =
            vm.envOr("SWAPBOT_VARIANT", string("swaprouter02"));
        bool is02 = keccak256(bytes(variant)) == keccak256("swaprouter02");
        bool isV1 = keccak256(bytes(variant)) == keccak256("swaprouter");
        require(is02 || isV1, "Deploy: unknown SWAPBOT_VARIANT");
        require(
            is02,
            "Deploy: original SwapRouter is not deployed on Sepolia; use swaprouter02"
        );
        require(SEPOLIA_ROUTER02.code.length > 0, "Deploy: router has no code");
        require(SEPOLIA_WETH.code.length > 0, "Deploy: WETH has no code");

        uint256 key = vm.envUint("SWAPBOT_PRIVATE_KEY");
        vm.startBroadcast(key);
        helper = address(new MultiHopSwap02(SEPOLIA_ROUTER02, SEPOLIA_WETH));
        vm.stopBroadcast();

        console2.log("deployer", vm.addr(key));
        console2.log("helper", helper);
    }
}
