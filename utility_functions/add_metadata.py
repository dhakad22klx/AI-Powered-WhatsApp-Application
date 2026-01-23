import subprocess
import os
import uuid

def inject_whatsapp_xmp_local(raw_webp: bytes, pack_name: str, publisher: str):
    output_dir = "stickers_output"
    os.makedirs(output_dir, exist_ok=True)
    
    uid = str(uuid.uuid4())[:8]
    # IMPORTANT: Use .webp extensions or webpmux will fail silently
    in_webp = os.path.join(output_dir, f"in_{uid}.webp")
    out_webp = os.path.join(output_dir, f"final_{uid}.webp")
    xmp_file = os.path.join(output_dir, f"meta_{uid}.xmp")

    # Save initial file
    with open(in_webp, "wb") as f: f.write(raw_webp)

    xmp_content = (
        f'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        f'<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.2">'
        f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        f'<rdf:Description rdf:about="" xmlns:wa="http://whatsapp.com/stickers/">'
        f'<wa:pack-id>{uuid.uuid4()}</wa:pack-id>'
        f'<wa:pack-name>{pack_name}</wa:pack-name>'
        f'<wa:publisher>{publisher}</wa:publisher>'
        f'<wa:is-animated>0</wa:is-animated>'
        f'</rdf:Description>'
        f'</rdf:RDF>'
        f'</x:xmpmeta>'
        f'<?xpacket end="r"?>'
    ).encode("utf-8")
    
    with open(xmp_file, "wb") as f: f.write(xmp_content)

    # COMMAND: Apply XMP (and optionally EXIF if you have exiftool)
    # webpmux -set xmp <file> <input> -o <output>
    subprocess.run(["webpmux", "-set", "xmp", xmp_file, in_webp, "-o", out_webp], check=True)

    with open(out_webp, "rb") as f:
        final_data = f.read()

    # CLEANUP
    os.remove(in_webp)
    os.remove(xmp_file)
    
    return final_data