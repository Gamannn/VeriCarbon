// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {VeriCarbon} from "../src/VeriCarbon.sol";

contract DeployVeriCarbon is Script {
    function run() external returns (VeriCarbon vc) {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        vc = new VeriCarbon();

        // Optional: grant the validator role to an additional validator at deploy time.
        // Set EXTRA_VALIDATOR to the address and the deploy will wire it up.
        try vm.envAddress("EXTRA_VALIDATOR") returns (address extra) {
            if (extra != address(0)) {
                vc.grantRole(vc.VALIDATOR_ROLE(), extra);
                console2.log("Granted VALIDATOR_ROLE to:", extra);
            }
        } catch {}

        vm.stopBroadcast();

        console2.log("VeriCarbon deployed at:", address(vc));
        console2.log("Deployer:", vm.addr(pk));
        console2.log("Admin, backend, validator roles all granted to deployer.");
    }
}
