import sys

class MemoryManager:
    def __init__(self, num_quadros, algoritmo):
        self.num_quadros = num_quadros
        self.algoritmo = algoritmo.upper()  # 'FIFO' ou 'LRU'
        
        # Tamanho da página em bytes (fixo em 256 bytes)
        self.page_size = 256
        self.offset_bits = 8  # 8 bits para offset
        
        # Tabela de páginas: mapeia cada página para um dicionário com { 'quadro': número_do_quadro, 'valido': True/False }
        self.page_table = {}
        
        # TLB: lista de entradas (cada uma é um dicionário com 'pagina' e 'quadro')
        self.tlb = []
        self.tlb_size = 16  # Tamanho fixo da TLB
        
        # Vetor que indica qual página está em cada quadro (se não houver, valor None)
        self.quadros = [None] * self.num_quadros
        
        # Vetor que armazena o conteúdo (bytes) de cada quadro, lido do BACKING_STORE
        self.physical_memory = [None] * self.num_quadros
        
        # Estruturas auxiliares para os algoritmos de substituição:
        self.fifo_queue = []   # Para FIFO: lista com as páginas na ordem de inserção
        self.uso_recente = {}  # Para LRU: dicionário { pagina: timestamp }
        
        # Estatísticas
        self.tlb_hits = 0
        self.page_faults = 0
        self.acessos = 0
        
        # Contador para o algoritmo LRU
        self.clock = 0

        # Abre o BACKING_STORE para leitura em modo binário
        try:
            self.backing_store = open("BACKING_STORE.bin", "rb")
        except Exception as e:
            print("Erro ao abrir BACKING_STORE.bin:", e)
            sys.exit(1)

    def carrega_pagina(self, pagina):
        """Lê uma página do BACKING_STORE.bin."""
        self.backing_store.seek(pagina * self.page_size)
        page_data = self.backing_store.read(self.page_size)
        if len(page_data) != self.page_size:
            print(f"Erro ao ler página {pagina} do BACKING_STORE.")
            sys.exit(1)
        return page_data

    def acessar(self, endereco_virtual):
        """Processa o acesso a um endereço virtual."""
        self.acessos += 1
        self.clock += 1

        endereco_virtual = endereco_virtual & 0xFFFF # Máscara para 16 bits

        # Divide o endereço virtual em número de página e offset
        pagina = (endereco_virtual >> self.offset_bits)
        offset = endereco_virtual & ((1 << self.offset_bits) - 1)

        # Procura na TLB
        quadro = self.buscar_na_tlb(pagina)
        if quadro is not None:
            self.tlb_hits += 1
        else:
            # Procura na tabela de páginas
            if pagina in self.page_table and self.page_table[pagina]['valido']:
                quadro = self.page_table[pagina]['quadro']
                self.atualiza_tlb(pagina, quadro)
            else:
                # Page fault
                self.page_faults += 1
                quadro = self.tratar_page_fault(pagina)
                self.page_table[pagina] = {'quadro': quadro, 'valido': True}
                self.atualiza_tlb(pagina, quadro)

        if self.algoritmo == "LRU":
            self.uso_recente[pagina] = self.clock

        # Calcula o endereço físico
        endereco_fisico = (quadro << self.offset_bits) | offset

        # Lê o conteúdo do endereço físico
        conteudo = self.ler_memoria(quadro, offset)
        return endereco_fisico, conteudo

    def buscar_na_tlb(self, pagina):
        """Procura a página na TLB."""
        # Retorna o quadro se a página está na TLB, ou None caso contrário

        for entrada in self.tlb:
            if entrada['pagina'] == pagina:
                return entrada['quadro']
        return None

    def atualiza_tlb(self, pagina, quadro):
        """Atualiza a TLB."""
        # Se a página já está na TLB, remove a entrada antiga
        # Adiciona a nova entrada

        if len(self.tlb) >= self.tlb_size:
            self.tlb.pop(0)
        self.tlb.append({'pagina': pagina, 'quadro': quadro})

    def tratar_page_fault(self, pagina):
        """Trata o page fault."""
        # Verifica se há um quadro livre
            # Se houver
                # pega indice do quadro livre
                # carrega a página do BACKING_STORE
                # insere a página na memória física no quadro livre
                # insere a página no dicionário de quadros
                # adiciona a página na fila (FIFO) ou dicionário de uso recente (LRU)
                # retorna o quadro livre
            # Se não houver
                # chama a função de substituição

        if None in self.quadros:
            quadro = self.quadros.index(None)
            page_data = self.carrega_pagina(pagina)
            self.physical_memory[quadro] = page_data
            self.quadros[quadro] = pagina
            if self.algoritmo == "FIFO":
                self.fifo_queue.append(pagina)
            elif self.algoritmo == "LRU":
                self.uso_recente[pagina] = self.clock
            return quadro
        else:
            if self.algoritmo == "FIFO":
                return self.substituicao_fifo(pagina)
            elif self.algoritmo == "LRU":
                return self.substituicao_lru(pagina)
            else:
                print("Algoritmo inválido.")
                sys.exit(1)

    def substituicao_fifo(self, pagina_nova):
        """Substituição FIFO."""
        # Remove a página mais antiga da fila
        # pega o quadro que será substituído
        # altero a validade da página que será substituída para False
        # removo a entrada da TLB
        # carrego a nova página
        # insiro a nova página na memoria fisica
        # adiciono a nova pagina no dicionário de quadros
        # adiciono a nova página na fila
        # retorno o quadro

        pagina_a_substituir = self.fifo_queue.pop(0)
        quadro = self.page_table[pagina_a_substituir]['quadro']
        self.page_table[pagina_a_substituir]['valido'] = False
        self.remover_da_tlb(pagina_a_substituir)

        page_data = self.carrega_pagina(pagina_nova)
        self.physical_memory[quadro] = page_data
        self.quadros[quadro] = pagina_nova

        self.fifo_queue.append(pagina_nova)
        return quadro

    def substituicao_lru(self, pagina_nova):
        """Substituição LRU."""
        # Pega a página menos recentemente usada
        # pega o quadro que será substituído
        # altero a validade da página que será substituída para False
        # removo a pagina da entrada da TLB
        # removo a página do dicionário de uso recente
        # carrego a nova página
        # insiro a nova página na memoria fisica
        # adiciono a nova pagina no dicionário de quadros
        # ajusto o tempo em que a nova página foi usada
        # retorno o quadro

        pagina_a_substituir = min(self.uso_recente, key=self.uso_recente.get)
        quadro = self.page_table[pagina_a_substituir]['quadro']
        self.page_table[pagina_a_substituir]['valido'] = False
        self.remover_da_tlb(pagina_a_substituir)
        del self.uso_recente[pagina_a_substituir]

        page_data = self.carrega_pagina(pagina_nova)
        self.physical_memory[quadro] = page_data
        self.quadros[quadro] = pagina_nova

        self.uso_recente[pagina_nova] = self.clock
        return quadro

    def remover_da_tlb(self, pagina):
        """Remove entradas da TLB."""
        # Remove todas as entradas da TLB para a página especificada
        self.tlb = [entrada for entrada in self.tlb if entrada['pagina'] != pagina]

    def ler_memoria(self, quadro, offset):
        """Lê o byte convertendo para signed."""
        # Lê o byte na posição especificada no quadro
        # Se o byte for maior que 127, converte para signed

        byte_value = self.physical_memory[quadro][offset]
        return byte_value - 256 if byte_value > 127 else byte_value

    def imprime_page_table(self, file=None):
        """Imprime a tabela de páginas."""
        if file is None:
            file = sys.stdout
        print("###########", file=file)
        print("Página - Quadro - Bit Validade", file=file)
        print("###########", file=file)
        for pagina in sorted(self.page_table.keys()):
            info = self.page_table[pagina]
            validade = 1 if info['valido'] else 0
            print(f"{pagina} - {info['quadro']} - {validade}", file=file)

    def imprime_tlb(self, file=None):
        """Imprime a TLB."""
        if file is None:
            file = sys.stdout
        print("************", file=file)
        print("Página - Quadro", file=file)
        print("************", file=file)
        for entrada in self.tlb:
            print(f"{entrada['pagina']} - {entrada['quadro']}", file=file)

    def imprime_estatisticas(self):
        """Imprime as estatísticas."""
        tlb_hit_rate = (self.tlb_hits / self.acessos) * 100 if self.acessos > 0 else 0
        page_fault_rate = (self.page_faults / self.acessos) * 100 if self.acessos > 0 else 0
        print("----- Estatísticas -----")
        print(f"Total de acessos: {self.acessos}")
        print(f"TLB Hits: {self.tlb_hits}  -> Taxa: {tlb_hit_rate:.2f}%")
        print(f"Page Faults: {self.page_faults}  -> Taxa: {page_fault_rate:.2f}%")

    def fechar_backing_store(self):
        """Fecha o BACKING_STORE."""
        if self.backing_store:
            self.backing_store.close()

def main():
    if len(sys.argv) != 4:
        print("Uso: python simulador.py address.txt [Quadros] [Alg Subst Página]")
        sys.exit(1)
    
    address_file = sys.argv[1]
    try:
        num_quadros = int(sys.argv[2])
        if(num_quadros != 128 and num_quadros != 256):
            print("Apenas 128 ou 256 quadros são suportados.")
            sys.exit(1)
    except ValueError:
        print("[Quadros] deve ser um inteiro.")
        sys.exit(1)
    
    algoritmo_substituicao = sys.argv[3].upper()
    if algoritmo_substituicao not in ["FIFO", "LRU"]:
        print("[Alg Subst Página] deve ser FIFO ou LRU.")
        sys.exit(1)
    
    memoria = MemoryManager(num_quadros, algoritmo_substituicao)
    
    # Limpa o arquivo correct.txt
    with open("correct.txt", "w"):
        pass
    
    try:
        with open(address_file, "r") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                if line.upper() == "PAGETABLE":
                    with open("correct.txt", "a") as saida:
                        memoria.imprime_page_table(saida)
                elif line.upper() == "TLB":
                    with open("correct.txt", "a") as saida:
                        memoria.imprime_tlb(saida)
                else:
                    try:
                        endereco_virtual = int(line)

                        endereco_fisico, conteudo = memoria.acessar(endereco_virtual)
                        with open("correct.txt", "a") as saida:
                            saida.write(f"Endereço Virtual: {endereco_virtual}  Endereço Físico: {endereco_fisico} Conteúdo: {conteudo}\n")
                    except ValueError:
                        print(f"Linha inválida: {line}")
    except FileNotFoundError:
        print(f"Arquivo {address_file} não encontrado.")
        sys.exit(1)
    
    #memoria.imprime_page_table()
    memoria.imprime_estatisticas()
    memoria.fechar_backing_store()

if __name__ == "__main__":
    main()