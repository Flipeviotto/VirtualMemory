import sys

class MemoryManager:
    def __init__(self, num_quadros, algoritmo):
        self.num_quadros = num_quadros
        self.algoritmo = algoritmo.upper()  # 'FIFO' ou 'LRU'
        
        # Tamanho da página em bytes (fixo em 256 bytes, conforme especificação)
        self.page_size = 256
        self.offset_bits = self.tamanho_offset()  # 8 bits
        
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
        
        # Um contador para o algoritmo LRU
        self.clock = 0

        # Abre o BACKING_STORE para leitura em modo binário
        try:
            self.backing_store = open("BACKING_STORE.bin", "rb")
        except Exception as e:
            print("Erro ao abrir BACKING_STORE.bin:", e)
            sys.exit(1)

    def tamanho_offset(self):
        """Calcula o número de bits do offset dado o tamanho da página."""
        # Exemplo: 256 bytes => log2(256) = 8 bits.
        return 8

    def carrega_pagina(self, pagina):
        """
        Lê uma página do BACKING_STORE.bin.
        O arquivo é organizado em páginas consecutivas de 256 bytes.
        """
        self.backing_store.seek(pagina * self.page_size)
        page_data = self.backing_store.read(self.page_size)
        if len(page_data) != self.page_size:
            print(f"Erro ao ler página {pagina} do BACKING_STORE.")
            sys.exit(1)
        return page_data

    def acessar(self, endereco_virtual):
        """
        Processa o acesso a um endereço virtual:
          - Divide o endereço em número de página e offset.
          - Procura a página na TLB e, se não encontrada, na tabela de páginas.
          - Em caso de page fault, lê a página do BACKING_STORE e a carrega em um quadro (livre ou por substituição).
          - Atualiza as estruturas (TLB, tabela de páginas, algoritmo de substituição).
          - Calcula o endereço físico e lê o conteúdo do quadro para o offset indicado.
        Retorna uma tupla: (endereço físico, conteúdo lido).
        """
        self.acessos += 1
        self.clock += 1

        # Divide o endereço virtual em número de página e offset
        pagina = self.obter_pagina(endereco_virtual)
        offset = self.obter_offset(endereco_virtual)

        # Procura na TLB
        quadro = self.buscar_na_tlb(pagina)
        if quadro is not None:
            # TLB hit
            self.tlb_hits += 1
        else:
            # Procura na tabela de páginas
            if pagina in self.page_table and self.page_table[pagina]['valido']:
                quadro = self.page_table[pagina]['quadro']
                self.atualiza_tlb(pagina, quadro)
            else:
                # Page fault: a página não está na memória
                self.page_faults += 1
                quadro = self.tratar_page_fault(pagina)
                # Atualiza (ou insere) a entrada na tabela de páginas
                self.page_table[pagina] = {'quadro': quadro, 'valido': True}
                self.atualiza_tlb(pagina, quadro)

        # Se o algoritmo for LRU, atualiza o timestamp de acesso da página
        if self.algoritmo == "LRU":
            self.uso_recente[pagina] = self.clock

        # Calcula o endereço físico: (quadro << offset_bits) | offset
        endereco_fisico = (quadro << self.offset_bits) | offset

        # Lê o conteúdo do endereço físico na memória (a partir do quadro carregado)
        conteudo = self.ler_memoria(quadro, offset)
        return endereco_fisico, conteudo

    def obter_pagina(self, endereco_virtual):
        """Retorna o número da página extraído do endereço virtual."""
        return endereco_virtual >> self.offset_bits

    def obter_offset(self, endereco_virtual):
        """Retorna o offset extraído do endereço virtual."""
        return endereco_virtual & ((1 << self.offset_bits) - 1)

    def buscar_na_tlb(self, pagina):
        """
        Procura a página na TLB.
        Retorna o número do quadro se a página estiver na TLB; caso contrário, retorna None.
        """
        for entrada in self.tlb:
            if entrada['pagina'] == pagina:
                return entrada['quadro']
        return None

    def atualiza_tlb(self, pagina, quadro):
        """
        Atualiza a TLB com a entrada (pagina, quadro).
        Se a TLB estiver cheia, remove a entrada mais antiga (FIFO).
        """
        if len(self.tlb) >= self.tlb_size:
            self.tlb.pop(0)
        self.tlb.append({'pagina': pagina, 'quadro': quadro})

    def tratar_page_fault(self, pagina):
        """
        Trata o page fault:
          - Se houver um quadro livre, carrega a página nele.
          - Caso contrário, utiliza o algoritmo de substituição (FIFO ou LRU) para liberar um quadro,
            carrega a página do BACKING_STORE e atualiza as estruturas.
        Retorna o número do quadro onde a página foi carregada.
        """
        if None in self.quadros:
            # Há um quadro livre
            quadro = self.quadros.index(None)
            # Carrega a página do BACKING_STORE
            page_data = self.carrega_pagina(pagina)
            self.physical_memory[quadro] = page_data
            self.quadros[quadro] = pagina
            # Atualiza estrutura de substituição
            if self.algoritmo == "FIFO":
                self.fifo_queue.append(pagina)
            elif self.algoritmo == "LRU":
                self.uso_recente[pagina] = self.clock
            return quadro
        else:
            # Nenhum quadro livre: realiza substituição
            if self.algoritmo == "FIFO":
                return self.substituicao_fifo(pagina)
            elif self.algoritmo == "LRU":
                return self.substituicao_lru(pagina)
            else:
                print("Algoritmo de substituição inválido.")
                sys.exit(1)

    def substituicao_fifo(self, pagina_nova):
        """
        Substituição utilizando FIFO:
          - Remove a página mais antiga da fila.
          - Obtém o quadro onde ela estava.
          - Marca a entrada da página substituída como inválida e remove da TLB.
          - Carrega a nova página do BACKING_STORE para esse quadro e atualiza a fila FIFO.
        Retorna o quadro onde a nova página foi carregada.
        """
        pagina_a_substituir = self.fifo_queue.pop(0)
        quadro = self.page_table[pagina_a_substituir]['quadro']
        self.page_table[pagina_a_substituir]['valido'] = False
        self.remover_da_tlb(pagina_a_substituir)

        # Carrega a nova página do BACKING_STORE
        page_data = self.carrega_pagina(pagina_nova)
        self.physical_memory[quadro] = page_data
        self.quadros[quadro] = pagina_nova

        self.fifo_queue.append(pagina_nova)
        return quadro

    def substituicao_lru(self, pagina_nova):
        """
        Substituição utilizando LRU:
          - Encontra a página com o menor timestamp de acesso.
          - Obtém o quadro onde ela estava.
          - Marca a entrada da página substituída como inválida, remove-a da TLB e do dicionário LRU.
          - Carrega a nova página do BACKING_STORE para esse quadro e atualiza o dicionário LRU.
        Retorna o quadro onde a nova página foi carregada.
        """
        pagina_a_substituir = min(self.uso_recente, key=self.uso_recente.get)
        quadro = self.page_table[pagina_a_substituir]['quadro']
        self.page_table[pagina_a_substituir]['valido'] = False
        self.remover_da_tlb(pagina_a_substituir)
        del self.uso_recente[pagina_a_substituir]

        # Carrega a nova página do BACKING_STORE
        page_data = self.carrega_pagina(pagina_nova)
        self.physical_memory[quadro] = page_data
        self.quadros[quadro] = pagina_nova

        self.uso_recente[pagina_nova] = self.clock
        return quadro

    def remover_da_tlb(self, pagina):
        """Remove todas as entradas da TLB referentes à página informada."""
        self.tlb = [entrada for entrada in self.tlb if entrada['pagina'] != pagina]

    def ler_memoria(self, quadro, offset):
        """
        Lê o conteúdo armazenado na memória física no quadro e offset especificados.
        Retorna o valor (inteiro) do byte correspondente.
        """
        if self.physical_memory[quadro] is None:
            print(f"Erro: Quadro {quadro} não contém dados.")
            sys.exit(1)
        return self.physical_memory[quadro][offset]

    def imprime_page_table(self):
        """
        Imprime a tabela de páginas no formato:
        ###########
        Página - Quadro - Bit Validade
        ###########
        <página> - <quadro> - <1 ou 0>
        """
        print("###########")
        print("Página - Quadro - Bit Validade")
        print("###########")
        for pagina in sorted(self.page_table.keys()):
            info = self.page_table[pagina]
            validade = 1 if info['valido'] else 0
            print(f"{pagina} - {info['quadro']} - {validade}")

    def imprime_tlb(self):
        """
        Imprime as entradas da TLB no formato:
        ************
        Página - Quadro
        ************
        <página> - <quadro>
        """
        print("************")
        print("Página - Quadro")
        print("************")
        for entrada in self.tlb:
            print(f"{entrada['pagina']} - {entrada['quadro']}")

    def imprime_estatisticas(self):
        """
        Imprime as estatísticas:
          - Total de acessos
          - Número de TLB hits e taxa de TLB hit
          - Número de page faults e taxa de page fault
        """
        tlb_hit_rate = (self.tlb_hits / self.acessos) * 100 if self.acessos > 0 else 0
        page_fault_rate = (self.page_faults / self.acessos) * 100 if self.acessos > 0 else 0
        print("----- Estatísticas -----")
        print(f"Total de acessos: {self.acessos}")
        print(f"TLB Hits: {self.tlb_hits}  -> Taxa: {tlb_hit_rate:.2f}%")
        print(f"Page Faults: {self.page_faults}  -> Taxa: {page_fault_rate:.2f}%")

    def fechar_backing_store(self):
        """Fecha o arquivo do BACKING_STORE."""
        if self.backing_store:
            self.backing_store.close()


def main():
    # Verifica se os 3 parâmetros foram informados: address.txt, [Quadros] e [Alg Subst Página]
    if len(sys.argv) != 4:
        print("Uso: python simulador.py address.txt [Quadros] [Alg Subst Página]")
        sys.exit(1)
    
    address_file = sys.argv[1]
    try:
        num_quadros = int(sys.argv[2])
    except ValueError:
        print("O parâmetro [Quadros] deve ser um número inteiro.")
        sys.exit(1)
    
    algoritmo_substituicao = sys.argv[3].upper()
    if algoritmo_substituicao not in ["FIFO", "LRU"]:
        print("O parâmetro [Alg Subst Página] deve ser 'FIFO' ou 'LRU'.")
        sys.exit(1)
    
    # Inicializa o gerenciador de memória virtual
    memoria = MemoryManager(num_quadros, algoritmo_substituicao)
    
    # Prepara (ou limpa) o arquivo de saída correct.txt
    try:
        with open("correct.txt", "w") as saida:
            saida.write("")
    except Exception as e:
        print("Erro ao preparar o arquivo correct.txt:", e)
        sys.exit(1)
    
    # Abre e processa o arquivo de endereços
    try:
        with open(address_file, "r") as file:
            for line in file:
                line = line.strip()
                if line == "":
                    continue
                # Verifica se a linha é um comando especial
                if line.upper() == "PAGETABLE":
                    memoria.imprime_page_table()
                elif line.upper() == "TLB":
                    memoria.imprime_tlb()
                else:
                    # Se não for comando, espera um endereço virtual (número inteiro)
                    try:
                        endereco_virtual = int(line)
                    except ValueError:
                        print(f"Linha inválida: {line}")
                        continue
                    
                    endereco_fisico, conteudo = memoria.acessar(endereco_virtual)
                    # Grava a saída no arquivo correct.txt
                    with open("correct.txt", "a") as saida:
                        saida.write(f"Endereço Virtual: {endereco_virtual}  Endereço Físico: {endereco_fisico} Conteúdo: {conteudo}\n")
    except FileNotFoundError:
        print(f"Arquivo {address_file} não encontrado.")
        sys.exit(1)
    
    # Imprime as estatísticas ao final
    memoria.imprime_estatisticas()
    memoria.fechar_backing_store()

if __name__ == "__main__":
    main()
