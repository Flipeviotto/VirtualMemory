import sys
from collections import deque, OrderedDict

# Constantes
PAGE_SIZE = 256
NUM_PAGES = 256
TLB_SIZE = 16

# Estruturas para TLB, tabela de páginas e memória física
TLB = OrderedDict()  # Usado para LRU
page_table = {}
physical_memory = bytearray(NUM_PAGES * PAGE_SIZE)
free_frames = deque(range(256))  # Quadros livres (128 quadros)

# Estatísticas
tlb_hits = 0
page_faults = 0

# Algoritmo de substituição de página (FIFO ou LRU)
page_replacement_algorithm = None

def initialize(num_frames):
    global TLB, page_table, physical_memory, free_frames
    TLB.clear()
    page_table = {i: None for i in range(NUM_PAGES)}
    physical_memory = bytearray(NUM_PAGES * PAGE_SIZE)
    free_frames = deque(range(num_frames))  # 128 quadros

def translate_address(logical_address, backing_store):
    global tlb_hits, page_faults

    page_number = (logical_address >> 8) & 0xFF
    offset = logical_address & 0xFF

    # Verifica TLB
    if page_number in TLB:
        tlb_hits += 1
        frame_number = TLB[page_number]
    else:
        # TLB Miss: consulta tabela de páginas
        if page_table[page_number] is not None:
            frame_number = page_table[page_number]
        else:
            # Page Fault: carrega página do backing store
            page_faults += 1
            if not free_frames:
                # Substituição de página
                if page_replacement_algorithm == "FIFO":
                    # Encontra a página mais antiga na tabela de páginas que está em uso
                    for replaced_page, frame in page_table.items():
                        if frame is not None:
                            frame_number = frame
                            page_table[replaced_page] = None  # Remove a página substituída
                            if replaced_page in TLB:
                                del TLB[replaced_page]  # Remove da TLB também
                            break
                elif page_replacement_algorithm == "LRU":
                    # Encontra a página menos recentemente usada na TLB
                    if TLB:
                        replaced_page = next(iter(TLB))
                        frame_number = TLB[replaced_page]
                        page_table[replaced_page] = None  # Remove a página substituída
                        del TLB[replaced_page]  # Remove da TLB também
                    else:
                        # Se a TLB estiver vazia, escolhe a primeira página válida na tabela de páginas
                        for replaced_page, frame in page_table.items():
                            if frame is not None:
                                frame_number = frame
                                page_table[replaced_page] = None  # Remove a página substituída
                                break
                else:
                    raise RuntimeError("Algoritmo de substituição inválido.")
            else:
                frame_number = free_frames.popleft()

            # Carrega a página do backing store
            backing_store.seek(page_number * PAGE_SIZE)
            page_data = backing_store.read(PAGE_SIZE)
            if len(page_data) != PAGE_SIZE:
                raise RuntimeError(f"Erro ao carregar página {page_number} do BACKING_STORE.bin")

            physical_memory[frame_number * PAGE_SIZE:(frame_number + 1) * PAGE_SIZE] = page_data
            page_table[page_number] = frame_number

        # Atualiza TLB (LRU)
        if page_number in TLB:
            TLB.move_to_end(page_number)
        else:
            if len(TLB) >= TLB_SIZE:
                TLB.popitem(last=False)  # Remove a entrada mais antiga (FIFO para TLB)
            TLB[page_number] = frame_number

    # Forma o endereço físico
    physical_address = (frame_number << 8) | offset
    value = physical_memory[physical_address]

    return physical_address, value

def print_page_table():
    print("###########")
    print("Página - Quadro - Bit Validade")
    for page, frame in page_table.items():
        validity = 1 if frame is not None else 0
        print(f"{page} - {frame} - {validity}")
    print("###########")

def print_tlb():
    print("************")
    print("Página - Quadro")
    for page, frame in TLB.items():
        print(f"{page} - {frame}")
    print("************")

def main():
    global page_replacement_algorithm

    if len(sys.argv) != 4:
        print("Uso: <executável> address.txt [Quadros] [Alg Subst Página]")
        print("Exemplo: python simulador.py address.txt 128 FIFO")
        return

    address_file = sys.argv[1]
    num_frames = int(sys.argv[2])
    page_replacement_algorithm = sys.argv[3].upper()

    #if num_frames != 128:
    #    print("Apenas 128 quadros são suportados.")
    #    return

    if page_replacement_algorithm not in ["FIFO", "LRU"]:
        print("Algoritmo de substituição deve ser FIFO ou LRU.")
        return

    initialize(num_frames)

    with open(address_file, "r") as addr_file, open("BACKING_STORE.bin", "rb") as backing_store:
        total_addresses = 0
        for line in addr_file:
            line = line.strip()
            if line == "PageTable":
                print_page_table()
            elif line == "TLB":
                print_tlb()
            else:
                logical_address = int(line)
                physical_address, value = translate_address(logical_address, backing_store)
                print(f"Endereço Virtual: {logical_address}  Endereço Físico: {physical_address} Conteúdo: {value}")
                total_addresses += 1

    # Estatísticas
    if total_addresses > 0:
        print("...")
        print(f"TLB Hit Rate: {(tlb_hits / total_addresses) * 100:.2f}%")
        print(f"Page Fault Rate: {(page_faults / total_addresses) * 100:.2f}%")
    else:
        print("Nenhum endereço foi processado.")

if __name__ == "__main__":
    main()