// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {VeriCarbon} from "../src/VeriCarbon.sol";
import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";

contract VeriCarbonTest is Test {
    VeriCarbon internal vc;

    address internal admin = address(0xA11CE);
    address internal backend = address(0xB4CE);
    address internal validator1 = address(0xB01);
    address internal validator2 = address(0xB02);
    address internal validator3 = address(0xB03);
    address internal attacker = address(0xBAD);

    bytes32 internal constant PROJECT_A = keccak256("project-a");
    bytes32 internal constant PROJECT_B = keccak256("project-b");
    bytes32 internal constant REGISTRY_HASH = keccak256("registry-refs");
    bytes32 internal constant DATASET_HASH = keccak256("dataset-v1");
    bytes32 internal constant MODEL_HASH = keccak256("model-v1");
    bytes32 internal constant RESULT_HASH = keccak256("result-v1");

    function setUp() public {
        vm.startPrank(admin);
        vc = new VeriCarbon();
        vc.grantRole(vc.BACKEND_ROLE(), backend);
        vc.grantRole(vc.VALIDATOR_ROLE(), validator1);
        vc.grantRole(vc.VALIDATOR_ROLE(), validator2);
        vc.grantRole(vc.VALIDATOR_ROLE(), validator3);
        vm.stopPrank();
    }

    // ──────────────────── Helpers ────────────────────
    function _cells(uint64 start, uint64 count) internal pure returns (uint64[] memory) {
        uint64[] memory c = new uint64[](count);
        for (uint64 i = 0; i < count; i++) c[i] = start + i;
        return c;
    }

    function _submit(bytes32 pid, uint64[] memory cells, uint64 areaHa) internal {
        vm.prank(backend);
        vc.submitProject(pid, cells, areaHa, REGISTRY_HASH);
    }

    function _attest(address v, bytes32 pid, uint64 verifiedHa, uint16 confBps) internal {
        vm.prank(v);
        vc.attestVerification(pid, DATASET_HASH, MODEL_HASH, RESULT_HASH, verifiedHa, confBps);
    }

    // ──────────────────── Submission tests ────────────────────
    function test_submitProject_setsPendingState() public {
        _submit(PROJECT_A, _cells(100, 5), 500);
        (, VeriCarbon.State state,,,,,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(state), uint256(VeriCarbon.State.Pending));
    }

    function test_submitProject_claimsCells() public {
        uint64[] memory cells = _cells(100, 3);
        _submit(PROJECT_A, cells, 500);
        for (uint64 i = 0; i < 3; i++) {
            assertEq(vc.getCellOwner(100 + i), PROJECT_A);
        }
    }

    function test_submitProject_revertsOnDuplicateCell() public {
        _submit(PROJECT_A, _cells(100, 5), 500);
        uint64[] memory overlapping = _cells(102, 3); // cells 102, 103, 104 overlap
        vm.prank(backend);
        vm.expectRevert(
            abi.encodeWithSelector(VeriCarbon.CellAlreadyClaimed.selector, uint64(102), PROJECT_A)
        );
        vc.submitProject(PROJECT_B, overlapping, 300, REGISTRY_HASH);
    }

    function test_submitProject_revertsOnEmptyCells() public {
        uint64[] memory empty = new uint64[](0);
        vm.prank(backend);
        vm.expectRevert(VeriCarbon.NoCells.selector);
        vc.submitProject(PROJECT_A, empty, 500, REGISTRY_HASH);
    }

    function test_submitProject_revertsOnZeroArea() public {
        vm.prank(backend);
        vm.expectRevert(VeriCarbon.ZeroArea.selector);
        vc.submitProject(PROJECT_A, _cells(100, 1), 0, REGISTRY_HASH);
    }

    function test_submitProject_revertsOnDuplicateProjectId() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(backend);
        vm.expectRevert(VeriCarbon.ProjectAlreadyExists.selector);
        vc.submitProject(PROJECT_A, _cells(200, 2), 500, REGISTRY_HASH);
    }

    function test_submitProject_revertsOnUnauthorized() public {
        vm.prank(attacker);
        vm.expectRevert();
        vc.submitProject(PROJECT_A, _cells(100, 1), 500, REGISTRY_HASH);
    }

    // ──────────────────── Attestation tests ────────────────────
    function test_attestation_advancesToVerifiedAtThreshold() public {
        _submit(PROJECT_A, _cells(100, 5), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        (, VeriCarbon.State s1,,,, uint8 c1,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s1), uint256(VeriCarbon.State.Pending));
        assertEq(c1, 1);

        _attest(validator2, PROJECT_A, 490, 8700);
        (, VeriCarbon.State s2, , uint64 verifiedHa, uint16 confBps, uint8 c2,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s2), uint256(VeriCarbon.State.Verified));
        assertEq(c2, 2);
        assertEq(verifiedHa, 485); // avg of 480, 490
        assertEq(confBps, 8600); // avg of 8500, 8700
    }

    function test_attestation_revertsOnDoubleAttestation() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        vm.prank(validator1);
        vm.expectRevert(VeriCarbon.AlreadyAttested.selector);
        vc.attestVerification(PROJECT_A, DATASET_HASH, MODEL_HASH, RESULT_HASH, 480, 8500);
    }

    function test_attestation_revertsOnUnauthorized() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(attacker);
        vm.expectRevert();
        vc.attestVerification(PROJECT_A, DATASET_HASH, MODEL_HASH, RESULT_HASH, 480, 8500);
    }

    function test_attestation_revertsOnOutOfRangeConfidence() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(validator1);
        vm.expectRevert(VeriCarbon.ConfidenceOutOfRange.selector);
        vc.attestVerification(PROJECT_A, DATASET_HASH, MODEL_HASH, RESULT_HASH, 480, 10001);
    }

    function test_attestation_revertsAfterVerified() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        _attest(validator2, PROJECT_A, 490, 8700);
        // state now Verified, further attestations should fail
        vm.prank(validator3);
        vm.expectRevert();
        vc.attestVerification(PROJECT_A, DATASET_HASH, MODEL_HASH, RESULT_HASH, 500, 9000);
    }

    // ──────────────────── Flag tests ────────────────────
    function test_flag_movesToFlaggedState() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(validator1);
        vc.flagProject(PROJECT_A, "suspected duplicate");
        (, VeriCarbon.State s,,,,,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s), uint256(VeriCarbon.State.Flagged));
    }

    function test_resolveFlag_acceptMovesBackToPending() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(validator1);
        vc.flagProject(PROJECT_A, "test flag");
        vm.prank(admin);
        vc.resolveFlag(PROJECT_A, true, new uint64[](0));
        (, VeriCarbon.State s,,,,,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s), uint256(VeriCarbon.State.Pending));
    }

    function test_resolveFlag_rejectReleasesCells() public {
        uint64[] memory cells = _cells(100, 3);
        _submit(PROJECT_A, cells, 500);
        vm.prank(validator1);
        vc.flagProject(PROJECT_A, "test flag");
        vm.prank(admin);
        vc.resolveFlag(PROJECT_A, false, cells);
        (, VeriCarbon.State s,,,,,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s), uint256(VeriCarbon.State.Rejected));
        // cells now free; another project can claim them
        _submit(PROJECT_B, cells, 400);
        assertEq(vc.getCellOwner(100), PROJECT_B);
    }

    // ──────────────────── Issue claim tests ────────────────────
    function test_issueClaim_fromVerified() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        _attest(validator2, PROJECT_A, 490, 8700);
        vm.prank(admin);
        vc.issueClaim(PROJECT_A);
        (, VeriCarbon.State s,,,,,,,,,) = vc.getProject(PROJECT_A);
        assertEq(uint256(s), uint256(VeriCarbon.State.Issued));
    }

    function test_issueClaim_revertsIfNotVerified() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        vm.prank(admin);
        vm.expectRevert();
        vc.issueClaim(PROJECT_A);
    }

    function test_issueClaim_revertsOnDoubleIssuance() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        _attest(validator2, PROJECT_A, 490, 8700);
        vm.prank(admin);
        vc.issueClaim(PROJECT_A);
        vm.prank(admin);
        vm.expectRevert();
        vc.issueClaim(PROJECT_A);
    }

    function test_issueClaim_revertsOnUnauthorized() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        _attest(validator2, PROJECT_A, 490, 8700);
        vm.prank(attacker);
        vm.expectRevert();
        vc.issueClaim(PROJECT_A);
    }

    // ──────────────────── Reject tests ────────────────────
    function test_reject_releasesCellsForReuse() public {
        uint64[] memory cells = _cells(100, 3);
        _submit(PROJECT_A, cells, 500);
        vm.prank(admin);
        vc.rejectProject(PROJECT_A, cells);
        _submit(PROJECT_B, cells, 400);
        assertEq(vc.getCellOwner(100), PROJECT_B);
    }

    function test_reject_cannotRejectIssuedProject() public {
        _submit(PROJECT_A, _cells(100, 2), 500);
        _attest(validator1, PROJECT_A, 480, 8500);
        _attest(validator2, PROJECT_A, 490, 8700);
        vm.prank(admin);
        vc.issueClaim(PROJECT_A);
        vm.prank(admin);
        vm.expectRevert();
        vc.rejectProject(PROJECT_A, _cells(100, 2));
    }

    // ──────────────────── Invariant: cell exclusivity under activity ────────────────────
    function testFuzz_submitNeverCreatesOverlap(uint64 startA, uint8 countA, uint64 startB, uint8 countB) public {
        countA = uint8(bound(countA, 1, 20));
        countB = uint8(bound(countB, 1, 20));
        // keep away from overflow
        startA = uint64(bound(startA, 1, 1_000_000));
        startB = uint64(bound(startB, 1, 1_000_000));

        uint64[] memory cellsA = _cells(startA, countA);
        _submit(PROJECT_A, cellsA, 100);

        uint64[] memory cellsB = _cells(startB, countB);

        // determine if ranges overlap
        bool overlap = !(startA + countA <= startB || startB + countB <= startA);

        if (overlap) {
            vm.prank(backend);
            vm.expectRevert();
            vc.submitProject(PROJECT_B, cellsB, 100, REGISTRY_HASH);
        } else {
            vm.prank(backend);
            vc.submitProject(PROJECT_B, cellsB, 100, REGISTRY_HASH);
            // sanity: no cell has two owners
            for (uint64 i = 0; i < countA; i++) {
                assertEq(vc.getCellOwner(startA + i), PROJECT_A);
            }
            for (uint64 i = 0; i < countB; i++) {
                assertEq(vc.getCellOwner(startB + i), PROJECT_B);
            }
        }
    }
}
