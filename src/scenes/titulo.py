"""Tela de título: JOGAR/CONTINUAR, NOVO JOGO, COMO JOGAR e SAIR. Ao começar, segue para o mundo e os diálogos do Seu Zeca."""
import json
import math

import pygame

from src.core.config import ALTURA, DATA, LARGURA, TILE, WEB
from src.core.tipos import Direcao
from src.scenes.base import Cena
from src.scenes.mundo import CenaMundo

CONFIRMAR = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_e)
CIMA, BAIXO = (pygame.K_UP, pygame.K_w), (pygame.K_DOWN, pygame.K_s)
TINTA, OURO, BRANCO, VERMELHO = (29, 39, 66), (255, 216, 94), (255, 255, 255), (229, 72, 77)
PAPEL = (255, 250, 240)
SAVE_SLOTS = [DATA / "save.json", DATA / "save_2.json", DATA / "save_3.json"]
COMANDOS = [
    ("SETAS ou WASD", "andar pelo mapa"),
    ("E, ESPAÇO ou ENTER", "falar com guias e ler placas"),
    ("B", "subir ou descer da bicicleta"),
    ("C", "abrir o caderno de curiosidades"),
    ("H (na pergunta)", "usar uma concha e eliminar uma resposta errada"),
    ("F3", "mostrar informações de depuração"),
    ("ESC", "voltar ao menu"),
]
Y_CHAO = ALTURA - 3 * TILE      # a faixa de areia e grama começa aqui
TEMPO_FADE = 0.35


class CenaTitulo(Cena):
    def __init__(self, jogo):
        super().__init__(jogo)
        rec = jogo.recursos
        self.tempo, self.saindo = 0.0, None
        self.tem_save = not WEB and any(p.exists() for p in SAVE_SLOTS)
        self.slot_selecionado = 0
        self.nome_digitado = ""
        self.modo = "menu"            # "menu", "confirma" (apagar progresso) ou "como" (tela de comandos)
        self.itens, self.sel = [], 0
        self._trocar_modo("menu")
        self.f_titulo, self.f_sub = pygame.font.Font(None, 104), pygame.font.Font(None, 30)
        self.f_botao, self.f_dica = pygame.font.Font(None, 40), pygame.font.Font(None, 24)
        self.agua = rec.imagem("mundo/agua.png")
        self.areia, self.grama = rec.terreno("areia")[(1, 1)], rec.terreno("grama")[(1, 1)]
        self.torre, self.casa = rec.imagem("mundo/torre_azul.png"), rec.imagem("mundo/casa_palha_1.png")
        self.placa, self.arbusto = rec.imagem("mundo/placa_seta.png"), rec.imagem("mundo/arbusto_3.png")
        self.sombra, self.bicicleta = rec.sombra(), rec.bicicleta()
        self.moradores = [(rec.personagem(f"NPC_{n}.png", tom), x) for n, tom, x in ((1, 0, 250), (5, 1, 330), (12, 2, 600))]
        self.fundo = self._montar_fundo()


    def _carregar_ranking(self):
        # NPCs são referências fixas; as pontuações reais vêm dos saves existentes.
        ranking = [
            ("Seu Zeca (NPC)", 1650),
            ("Guia da Lagoa (NPC)", 1400),
            ("Ciclista de Itaipuaçu (NPC)", 1200),
        ]
        for caminho in SAVE_SLOTS:
            try:
                if caminho.exists():
                    dados = json.loads(caminho.read_text(encoding="utf-8"))
                    nome = str(dados.get("nome_jogador", "Ciclista"))[:18] or "Ciclista"
                    melhores = dados.get("melhores", [])
                    pontos = sum(v for v in melhores if isinstance(v, int) and not isinstance(v, bool))
                    ranking.append((nome, pontos))
            except (OSError, ValueError, TypeError):
                continue
        melhores_por_nome = {}
        for nome, pontos in ranking:
            melhores_por_nome[nome] = max(pontos, melhores_por_nome.get(nome, -1))
        return sorted(melhores_por_nome.items(), key=lambda item: item[1], reverse=True)[:8]

    def _montar_fundo(self):
        s = pygame.Surface((LARGURA, ALTURA))
        for y in range(0, ALTURA, TILE):
            for x in range(0, LARGURA, TILE):
                s.blit(self.agua, (x, y))
        for x in range(0, LARGURA, TILE):
            s.blit(self.areia, (x, Y_CHAO))
            s.blit(self.grama, (x, Y_CHAO + TILE))
            s.blit(self.grama, (x, Y_CHAO + 2 * TILE))
        return s

    # ---------- menus ----------
    def _trocar_modo(self, modo):
        self.modo = modo
        if modo == "menu":
            self.itens = (["CONTINUAR", "NOVO JOGO"] if self.tem_save else ["NOVO JOGO"]) + ["RANKING", "COMO JOGAR"] + ([] if WEB else ["SAIR"])
            self.sel = 0
        elif modo in ("slots_carregar", "slots_novo"):
            self.itens = [f"SLOT {i + 1}" + (" — ocupado" if p.exists() else " — vazio")
                          for i, p in enumerate(SAVE_SLOTS)] + ["VOLTAR"]
            self.sel = 0
        elif modo == "ranking":
            self.itens, self.sel = [], 0
            self.ranking = self._carregar_ranking()
        elif modo == "nome":
            self.itens, self.sel = [], 0
        elif modo == "confirma":
            self.itens, self.sel = ["SOBRESCREVER SLOT", "VOLTAR"], 1
        else:
            self.itens, self.sel = [], 0
        self.botoes = [pygame.Rect(LARGURA // 2 - 180, 290 + i * 66, 360, 54) for i in range(len(self.itens))]

    def _escolher(self):
        acao = self.itens[self.sel]
        if acao == "CONTINUAR":
            self._trocar_modo("slots_carregar")
        elif acao in ("NOVO JOGO", "JOGAR"):
            self._trocar_modo("slots_novo")
        elif self.modo in ("slots_carregar", "slots_novo") and acao.startswith("SLOT "):
            self.slot_selecionado = int(acao[5]) - 1
            caminho = SAVE_SLOTS[self.slot_selecionado]
            if self.modo == "slots_carregar":
                if caminho.exists():
                    self.jogo.save_path = caminho
                    self.jogo.player_name = ""
                    self.saindo = 0.0
            elif caminho.exists():
                self._trocar_modo("confirma")
            else:
                self.nome_digitado = ""
                self._trocar_modo("nome")
        elif acao == "SOBRESCREVER SLOT":
            SAVE_SLOTS[self.slot_selecionado].unlink(missing_ok=True)
            self.nome_digitado = ""
            self._trocar_modo("nome")
        elif acao == "VOLTAR":
            self._trocar_modo("menu")
        elif acao == "RANKING":
            self._trocar_modo("ranking")
        elif acao == "COMO JOGAR":
            self._trocar_modo("como")
        elif acao == "SAIR":
            self.jogo.rodando = False

    # ---------- eventos ----------
    def processar_evento(self, ev):
        if self.saindo is not None:
            return
        if self.modo == "nome":
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    self.jogo.save_path = SAVE_SLOTS[self.slot_selecionado]
                    self.jogo.player_name = self.nome_digitado.strip()[:18] or "Ciclista"
                    self.saindo = 0.0
                elif ev.key == pygame.K_BACKSPACE:
                    self.nome_digitado = self.nome_digitado[:-1]
                elif ev.unicode and ev.unicode.isprintable() and len(self.nome_digitado) < 18:
                    proibidos = chr(92) + '/:*?' + chr(34) + '<>|'
                    if not any(ch in proibidos for ch in ev.unicode):
                        self.nome_digitado += ev.unicode
            return
        if self.modo in ("como", "ranking"):
            if (ev.type == pygame.KEYDOWN and ev.key in CONFIRMAR + (pygame.K_BACKSPACE,)) or (
                    ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self._trocar_modo("menu")
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key in CIMA and self.itens:
                self.sel = (self.sel - 1) % len(self.itens)
            elif ev.key in BAIXO and self.itens:
                self.sel = (self.sel + 1) % len(self.itens)
            elif ev.key in CONFIRMAR and self.itens:
                self._escolher()
            elif ev.key == pygame.K_BACKSPACE and self.modo in ("confirma", "slots_carregar", "slots_novo"):
                self._trocar_modo("menu")
        elif ev.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.botoes):
                if r.collidepoint(ev.pos):
                    self.sel = i
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.botoes):
                if r.collidepoint(ev.pos):
                    self.sel = i
                    self._escolher()

    def atualizar(self, dt):
        self.tempo += dt
        if self.saindo is not None:
            self.saindo += dt
            if self.saindo >= TEMPO_FADE:
                self.jogo.cena = CenaMundo(self.jogo)   # a introdução do Seu Zeca começa aqui

    # ---------- desenho ----------
    def _texto(self, fonte, texto, cor, centro, sombra=TINTA, desloc=3):
        if sombra:
            tela_s = fonte.render(texto, True, sombra)
            self._tela.blit(tela_s, tela_s.get_rect(center=(centro[0] + desloc, centro[1] + desloc)))
        img = fonte.render(texto, True, cor)
        self._tela.blit(img, img.get_rect(center=centro))

    def _painel_comandos(self, tela):
        caixa = pygame.Rect(60, 200, LARGURA - 120, 380)
        pygame.draw.rect(tela, TINTA, caixa.move(6, 6))
        pygame.draw.rect(tela, PAPEL, caixa)
        pygame.draw.rect(tela, TINTA, caixa, 4)
        self._texto(self.f_botao, "COMO JOGAR", VERMELHO, (caixa.centerx, caixa.top + 34), sombra=None)
        meta = self.f_dica.render("Converse com os guias, acerte as perguntas, vença os chefões e reacenda o Farol.", True, TINTA)
        tela.blit(meta, meta.get_rect(center=(caixa.centerx, caixa.top + 72)))
        for i, (tecla, texto) in enumerate(COMANDOS):
            y = caixa.top + 112 + i * 38
            tela.blit(self.f_sub.render(tecla, True, VERMELHO), (caixa.left + 30, y))
            tela.blit(self.f_sub.render(texto, True, TINTA), (caixa.left + 300, y))

    def desenhar(self, tela):
        self._tela = tela
        t = self.tempo
        tela.blit(self.fundo, (0, 0))
        base = Y_CHAO + 30
        tela.blit(self.casa, (70, base - self.casa.get_height()))
        tela.blit(self.torre, (772, base - self.torre.get_height()))
        if int(t * 1.6) % 2 == 0:     # lâmpada do farol piscando fraca: ele ainda está apagado
            pygame.draw.circle(tela, OURO, (772 + 64, base - 214), 12)
        tela.blit(self.placa, (470, base - 96))
        tela.blit(self.arbusto, (210, base - 46))
        for folha, x in self.moradores:
            tela.blit(self.sombra, (x + 10, base + 38))
            tela.blit(folha.quadro(Direcao.BAIXO, False, t), (x, base - 12))
        # ciclista cruzando a areia, de ponta a ponta
        bx = (t * 130) % (LARGURA + 160) - 100
        tela.blit(self.bicicleta.quadro(True, t, Direcao.DIREITA), (bx, Y_CHAO - 34))

        self._texto(self.f_titulo, "PEDALA, MARICÁ!", BRANCO, (LARGURA // 2, 96), desloc=5)
        self._texto(self.f_sub, "Um RPG sobre a história, a natureza e a cultura de Maricá (RJ)", OURO, (LARGURA // 2, 168))

        if self.modo == "ranking":
            caixa = pygame.Rect(170, 205, LARGURA - 340, 350)
            pygame.draw.rect(tela, TINTA, caixa.move(5, 5))
            pygame.draw.rect(tela, PAPEL, caixa)
            pygame.draw.rect(tela, TINTA, caixa, 4)
            self._texto(self.f_botao, "RANKING DOS CICLISTAS", VERMELHO, (caixa.centerx, caixa.top + 30), sombra=None)
            for i, (nome, pontos) in enumerate(self.ranking):
                y = caixa.top + 76 + i * 30
                cor = OURO if i == 0 else TINTA
                tela.blit(self.f_sub.render(f"{i + 1:>2}º  {nome}", True, cor), (caixa.left + 28, y))
                valor = self.f_sub.render(f"{pontos} pts", True, cor)
                tela.blit(valor, (caixa.right - 28 - valor.get_width(), y))
            dica_ranking = self.f_dica.render("NPCs são referências; jogadores vêm dos saves deste computador.", True, TINTA)
            tela.blit(dica_ranking, dica_ranking.get_rect(center=(caixa.centerx, caixa.bottom - 18)))
        if self.modo == "confirma":
            self._texto(self.f_sub, "Este slot já tem progresso. Sobrescrever?", BRANCO, (LARGURA // 2, 250))
        if self.modo in ("slots_carregar", "slots_novo"):
            self._texto(self.f_sub, "Escolha um slot para sua partida.", BRANCO, (LARGURA // 2, 240))
        if self.modo == "nome":
            self._texto(self.f_sub, "Digite o nome do personagem e pressione ENTER", BRANCO, (LARGURA // 2, 260))
            self._texto(self.f_botao, self.nome_digitado + ("_" if int(self.tempo * 2) % 2 == 0 else ""),
                        OURO, (LARGURA // 2, 330))
        if self.modo == "como":
            self._painel_comandos(tela)
        for i, (rot, r) in enumerate(zip(self.itens, self.botoes)):
            ativo = i == self.sel
            pygame.draw.rect(tela, TINTA, r.move(5, 5))
            pygame.draw.rect(tela, VERMELHO if ativo else PAPEL, r)
            pygame.draw.rect(tela, TINTA, r, 4)
            self._texto(self.f_botao, rot, BRANCO if ativo else TINTA, r.center, sombra=None)
            if ativo:
                x, y = r.left - 28 + 4 * math.sin(t * 8), r.centery
                seta = [(x, y - 12), (x + 18, y), (x, y + 12)]
                pygame.draw.polygon(tela, OURO, seta)
                pygame.draw.polygon(tela, TINTA, seta, 3)
        dica = {"menu": "SETAS escolhem   ·   ENTER confirma",
                "slots_carregar": "SETAS escolhem   ·   ENTER carrega   ·   BACKSPACE volta",
                "slots_novo": "SETAS escolhem   ·   ENTER seleciona slot   ·   BACKSPACE volta",
                "nome": "ENTER confirma o nome   ·   BACKSPACE apaga",
                "confirma": "ENTER sobrescreve   ·   BACKSPACE volta",
                "como": "ENTER ou clique para voltar",
                "ranking": "ENTER ou clique para voltar ao menu"}[self.modo]
        self._texto(self.f_dica, dica, BRANCO, (LARGURA // 2, ALTURA - 24))
        if self.saindo is not None:
            veu = pygame.Surface((LARGURA, ALTURA))
            veu.set_alpha(min(255, int(255 * self.saindo / TEMPO_FADE)))
            tela.blit(veu, (0, 0))
