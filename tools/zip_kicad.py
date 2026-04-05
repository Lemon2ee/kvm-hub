import zipfile, os
d = os.path.join(os.path.dirname(__file__), "..", "hardware")
out = os.path.join(d, "kvm_switch_kicad.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in ["kvm_switch.kicad_pro", "kvm_switch.kicad_sch", "kvm_switch.kicad_pcb"]:
        zf.write(os.path.join(d, f), f)
print(f"Created: {out}")
