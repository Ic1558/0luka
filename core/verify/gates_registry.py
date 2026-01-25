from core.verify.gates_v0 import gate_fs_purity, gate_hash_match, gate_proc_clean

GATES = {
    "gate.fs.purity": gate_fs_purity,
    "gate.hash.match": gate_hash_match,
    "gate.proc.clean": gate_proc_clean,
}
