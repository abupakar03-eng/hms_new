import struct

def get_imported_dlls(pe_path):
    with open(pe_path, 'rb') as f:
        data = f.read()
    
    # Verify DOS header
    if data[:2] != b'MZ':
        print("Not a valid PE file (no MZ header)")
        return
        
    # Get PE header offset
    pe_offset = struct.unpack('<I', data[0x3c:0x40])[0]
    pe_signature = data[pe_offset:pe_offset+4]
    if pe_signature != b'PE\x00\x00':
        print("Not a valid PE file (no PE signature)")
        return
        
    # Coff header
    machine = struct.unpack('<H', data[pe_offset+4:pe_offset+6])[0]
    is_64bit = (machine == 0x8664)
    
    # Optional header offset
    opt_header_offset = pe_offset + 24
    
    # Data directories offset in optional header
    # For PE32 (32-bit), it is at offset 96. For PE32+ (64-bit), it is at offset 112.
    dir_offset = opt_header_offset + (112 if is_64bit else 96)
    
    # Import directory RVA and size
    import_rva, import_size = struct.unpack('<II', data[dir_offset+8:dir_offset+16])
    if import_rva == 0 or import_size == 0:
        print("No import directory")
        return
        
    # Let's find the section containing import directory
    num_sections = struct.unpack('<H', data[pe_offset+6:pe_offset+8])[0]
    section_headers_offset = opt_header_offset + (240 if is_64bit else 224)
    
    import_section = None
    for i in range(num_sections):
        sec_offset = section_headers_offset + i * 40
        sec_name = data[sec_offset:sec_offset+8].rstrip(b'\x00').decode('utf-8', errors='ignore')
        vsize, vaddr, raw_size, raw_ptr = struct.unpack('<IIII', data[sec_offset+8:sec_offset+24])
        
        if vaddr <= import_rva < vaddr + vsize:
            import_section = (vaddr, raw_ptr)
            break
            
    if not import_section:
        print("Import section not found")
        return
        
    vaddr_start, raw_ptr_start = import_section
    import_offset = import_rva - vaddr_start + raw_ptr_start
    
    # Parse Import Directory Table
    dlls = []
    curr_offset = import_offset
    while True:
        # Import Lookup Table RVA, Time Date Stamp, Forwarder Chain, Name RVA, Import Address Table RVA
        ilt_rva, tds, fc, name_rva, iat_rva = struct.unpack('<IIIII', data[curr_offset:curr_offset+20])
        if ilt_rva == 0 and name_rva == 0:
            break
            
        # Get DLL Name
        dll_name_offset = name_rva - vaddr_start + raw_ptr_start
        dll_name = ""
        while data[dll_name_offset] != 0:
            dll_name += chr(data[dll_name_offset])
            dll_name_offset += 1
            
        dlls.append(dll_name)
        curr_offset += 20
        
    return dlls

if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"d:\H\bin\pgsql\bin\initdb.exe"
    print("Imports for:", path)
    for dll in sorted(get_imported_dlls(path)):
        print(" -", dll)

