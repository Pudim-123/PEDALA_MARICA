"""Cena de exploração: andar de bicicleta, conversar com guias, ler placas e conquistar selos."""
import json
import random

import pygame

from src.core.camera import Camera
from src.core.config import ALTURA, DATA, JOGADOR_FOLHA, JOGADOR_TOM, LARGURA, TEMPO_PASSO, TILE, WEB
from src.core.entrada import EntradaDirecional
from src.core.tipos import Direcao
from src.entities.jogador import Jogador
from src.entities.npc import NPC
from src.scenes.base import Cena
from src.systems.desafios import criar_desafio
from src.systems.perguntas import carregar_perguntas, verificar_npcs
from src.systems.pontuacao import MAXIMO_TOTAL, MINIMO_ACERTOS, PERGUNTAS_POR_FASE, TOTAL_FASES
from src.systems.progresso import Progresso
from src.ui.conversa import CONFIRMAR, Conversa
from src.ui.desafio import DesafioUI
from src.ui.texto import quebrar
from src.world.mapa import Mapa
from src.world.objetos import CATALOGO
from src.world.render_chao import montar_superficie_chao

COR_FUNDO, OURO = (29, 111, 165), (255, 200, 60)
DESLOC_SPRITE_Y = -10
TEMPO_BIKE = 0.11            # segundos por tile de bicicleta (a pé: TEMPO_PASSO)
FASES = range(1, TOTAL_FASES + 1)


class _Colisao:
    """Mapa + NPCs (que bloqueiam a passagem)."""

    def __init__(self, mapa, bloqueios):
        self.mapa, self.bloqueios = mapa, bloqueios

    def caminhavel(self, col, linha):
        return (col, linha) not in self.bloqueios and self.mapa.caminhavel(col, linha)


class CenaMundo(Cena):
    def __init__(self, jogo, caminho_mapa=DATA / "mapas" / "marica.json"):
        super().__init__(jogo)
        rec = jogo.recursos
        self.mapa = Mapa.carregar(caminho_mapa)
        dados = self.mapa.dados
        self.hist = json.loads((DATA / "historia.json").read_text(encoding="utf-8"))
        self.perguntas = carregar_perguntas(DATA / "perguntas.json")
        verificar_npcs(dados.get("npcs", []), self.perguntas)
        self.progresso = Progresso(None if WEB else (getattr(jogo, "save_path", None) or DATA / "save.json"),
                                     getattr(jogo, "player_name", "") or "Ciclista")
        self.progresso.carregar()
        self.jogo.player_name = self.progresso.nome_jogador
        for f in FASES:
            if f"boss_{f}" in self.progresso.bosses:
                self.mapa.liberar(f)
        self.npcs = [NPC(n["id"], n["nome"], n["col"], n["linha"], rec.personagem(n["folha"], n.get("tom", 0)),
                         Direcao[n.get("dir", "baixo").upper()], n.get("fase", 0), n.get("pergunta"),
                         n.get("fala", ""), n.get("papel", "guia"), n.get("falas", []), n.get("extras", []))
                     for n in dados.get("npcs", [])]
        self.npc_em = {(n.col, n.linha): n for n in self.npcs}
        self.npc_id = {n.id: n for n in self.npcs}
        self.chefoes = json.loads((DATA / "chefoes.json").read_text(encoding="utf-8"))
        self.desafio, self.caca = None, None
        self.pois = {(p["col"], p["linha"]): p for p in dados.get("pois", [])}
        self.total_curiosidades = len({p["id"] for p in self.pois.values() if p.get("curiosidade")})
        self.zonas = dados.get("zonas", [])
        self.conchas_mapa = {(c["col"], c["linha"]): c["id"] for c in dados.get("conchas", [])}
        self.aviso = ("", 0.0)
        self.colisao = _Colisao(self.mapa, set(self.npc_em))
        self.chao = montar_superficie_chao(self.mapa, rec)
        self.jogador = Jogador(*self.mapa.inicio, direcao=Direcao.CIMA)
        self.folha = rec.personagem(JOGADOR_FOLHA, JOGADOR_TOM)
        self.bicicleta = rec.bicicleta()
        self.sombra = rec.sombra()
        self.camera = Camera(LARGURA, ALTURA, self.mapa.largura_px, self.mapa.altura_px)
        self.entrada = EntradaDirecional()
        self.fonte, self.fonte_p = pygame.font.Font(None, 30), pygame.font.Font(None, 24)
        self.conversa = Conversa(self.fonte, self.fonte_p)
        self.hud_fundo = pygame.Surface((372, 120), pygame.SRCALPHA)
        self.hud_fundo.fill((24, 41, 56, 205))
        self.bike, self.debug = False, False
        self._seguir_jogador()
        if not self.progresso.intro_vista:
            self._intro()

    # ---------- eventos ----------
    def processar_evento(self, ev):
        self.entrada.processar_evento(ev)
        if self.desafio and self.desafio.ativo:
            self.desafio.evento(ev)
        elif self.conversa.ativa:
            self.conversa.evento(ev)
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_F3:
                self.debug = not self.debug
            elif ev.key == pygame.K_b:
                self.bike = not self.bike
                self.jogador.tempo_passo = TEMPO_BIKE if self.bike else TEMPO_PASSO
            elif ev.key == pygame.K_c:
                self._caderno()
            elif ev.key in CONFIRMAR:
                self._interagir()

    def _interagir(self):
        j = self.jogador
        if j.andando:
            return
        alvo = (j.col + j.direcao.dx, j.linha + j.direcao.dy)
        if alvo in self.npc_em:
            npc = self.npc_em[alvo]
            npc.virar_para(j.col, j.linha)
            self._falar_com(npc)
        elif alvo in self.pois:
            self._ler_poi(self.pois[alvo])

    # ---------- história e conversas ----------
    @staticmethod
    def _falas(nome, textos):
        return [{"tipo": "fala", "nome": nome, "texto": t} for t in textos]

    def _todas_concluidas(self):
        return all(f"boss_{f}" in self.progresso.bosses for f in FASES)

    def _fase_atual(self):
        return next((f for f in FASES if f"boss_{f}" not in self.progresso.bosses), TOTAL_FASES)

    def _intro(self):
        def fim():
            self.progresso.intro_vista = True
            self.progresso.salvar()
        self.conversa.iniciar(self._falas("Seu Zeca", self.hist["zeca"]["missao"]), fim)

    def _falar_com(self, npc):
        if npc.papel == "mentor":
            return self._conversa_zeca()
        if npc.papel == "chefe":
            return self._chefe(npc)
        if npc.papel == "conversa":
            return self._conversa_livre(npc)
        p = self.progresso
        if p.ja_respondeu(npc.fase, npc.id):
            return self.conversa.iniciar(self._falas(npc.nome, [self.hist["ja_respondeu"]]))
        pool = [npc.pergunta, *npc.extras]      # a cada nova tentativa, a próxima pergunta do guia
        q = self.perguntas[pool[p.tentativas.get(npc.id, 0) % len(pool)]]

        def ajuda():
            certas = [i for i in range(len(q.alternativas)) if i != q.correta and i not in self.conversa.ocultas]
            if p.conchas <= 0 or len(q.alternativas) - len(self.conversa.ocultas) <= 2 or not certas:
                return None
            p.conchas -= 1
            p.salvar()
            return random.choice(certas)

        def ao_escolher(idx):
            res = self.progresso.responder(npc.fase, npc.id, idx == q.correta)
            self.progresso.salvar()
            if res:
                self.conversa.inserir(self._itens_fim_fase(npc.fase, res))

        itens = self._falas(npc.nome, [npc.fala]) + [{
            "tipo": "escolha", "nome": npc.nome, "texto": q.texto, "opcoes": list(q.alternativas),
            "correta": q.correta, "explicacao": q.explicacao, "fonte": q.fonte_titulo,
            "ao_escolher": ao_escolher, "ajuda": ajuda,
            "rotulo": lambda: f"H: usar concha ({p.conchas})"}]
        self.conversa.iniciar(itens)

    def _conversa_livre(self, npc):
        p, cid = self.progresso, "presente_" + npc.id
        itens = self._falas(npc.nome, npc.falas)
        if cid not in p.conchas_coletadas:
            p.conchas_coletadas.add(cid)
            p.conchas += 1
            p.salvar()
            itens += self._falas("", ["Você ganhou 1 concha! Na hora da pergunta, aperte H para eliminar uma resposta errada."])
        self.conversa.iniciar(itens)

    def _caderno(self):
        p = self.progresso
        rec = " · ".join(f"F{f} {p.placar.melhor(f)}" for f in FASES)
        resumo = (f"Selos: {sum(f"boss_{f}" in p.bosses for f in FASES)}/{TOTAL_FASES}. Recordes: {rec}. "
                  f"Conchas: {p.conchas}. Curiosidades: {len(p.curiosidades)}/{self.total_curiosidades}.")
        itens = self._falas("Caderno", [resumo])
        vistos = {poi["id"]: poi for poi in self.pois.values() if poi["id"] in p.curiosidades}
        for poi in vistos.values():
            itens += self._falas(poi["titulo"], [poi["texto"]])
        self.conversa.iniciar(itens)

    def _itens_fim_fase(self, fase, res):
        info = self.hist["fases"][fase - 1]
        if not res["aprovada"]:     # menos de MINIMO_ACERTOS: a fase recomeça (recorde fica guardado)
            self.progresso.reiniciar_fase(fase)
            self.progresso.salvar()
            return self._falas("", [
                f"Você acertou {res['acertos']} de {PERGUNTAS_POR_FASE}. Para passar de região são necessários "
                f"pelo menos {MINIMO_ACERTOS}. Os guias vão perguntar de novo, e alguns trocam de pergunta. "
                "Leia as placas e junte conchas!"])
        txt = (f"Você acertou {res['acertos']} de {PERGUNTAS_POR_FASE} e fez {res['pontos']} pontos. "
               "Você passou nas perguntas!")
        txt += " Fase perfeita!" if res["perfeita"] else ""
        txt += "" if res["melhorou"] else f" Seu recorde nesta fase segue em {res['recorde']}."
        if f"boss_{fase}" in self.progresso.bosses:
            return self._falas("", [txt])
        return self._falas("", [txt, f"Agora enfrente o chefão: {self.npc_id[f'boss_{fase}'].nome}. {info['onde']}"])

    def _chefe(self, npc):
        p, cfg = self.progresso, self.chefoes[npc.id]
        if npc.id in p.bosses:
            return self.conversa.iniciar(self._falas(npc.nome, [cfg["ja_venceu"]]))
        if not p.placar.aprovada(npc.fase):
            return self.conversa.iniciar(self._falas(npc.nome, [cfg["trancado"]]))

        def comecar():
            self.desafio = DesafioUI(self.fonte, self.fonte_p, criar_desafio(cfg["desafio"]),
                                     lambda venceu: self._fim_chefe(npc, cfg, venceu), npc.nome)
        self.conversa.iniciar(self._falas(npc.nome, cfg["intro"]), comecar)

    def _fim_chefe(self, npc, cfg, venceu):
        p, info = self.progresso, self.hist["fases"][npc.fase - 1]
        if not venceu:
            return self.conversa.iniciar(self._falas(npc.nome, [cfg["derrota"]]))
        p.bosses.add(npc.id)
        p.salvar()
        itens = self._falas(npc.nome, cfg["vitoria"]) + self._falas("", [f"Selo conquistado: {info['selo']}!"])
        if self.mapa.liberar(npc.fase):
            itens += self._falas("", ["A passagem para a próxima região se abriu!"])
        self.conversa.iniciar(itens + self._falas("Seu Zeca", info["conclusao"]))

    def _conversa_zeca(self):
        p, h = self.progresso, self.hist
        if "final" in p.bosses:
            def refazer(i):
                if i < TOTAL_FASES:
                    p.reiniciar_fase(i + 1)
                    p.salvar()
                    self.conversa.inserir(self._falas("Seu Zeca", [h["zeca"]["refazendo"].format(fase=i + 1)]))
            itens = self._falas("Seu Zeca", h["zeca"]["completo"]) + [{
                "tipo": "escolha", "nome": "Seu Zeca", "texto": "Quer refazer alguma fase para bater seu recorde?",
                "opcoes": [f"Refazer fase {i}" for i in FASES] + ["Agora não"], "correta": None,
                "ao_escolher": refazer}]
            return self.conversa.iniciar(itens)
        if self._todas_concluidas():
            return self.conversa.iniciar(self._falas("Seu Zeca", [h["zeca"]["farol"]]))
        fase = self._fase_atual()
        info = h["fases"][fase - 1]
        if p.placar.aprovada(fase):
            txt = h["zeca"]["chefe"].format(fase=fase, chefe=self.npc_id[f"boss_{fase}"].nome, onde=info["onde"])
        else:
            txt = h["zeca"]["andamento"].format(fase=fase, nome=info["nome"], feitas=p.respondidas(fase),
                                                total=PERGUNTAS_POR_FASE, dica=info["dica"])
        self.conversa.iniciar(self._falas("Seu Zeca", [txt]))

    def _texto_farol_aceso(self):
        p = self.progresso
        rank = next(nome for minimo, nome in self.hist["ranks"] if p.placar.total >= minimo)
        return self.hist["farol_aceso"].format(total=p.placar.total, maximo=MAXIMO_TOTAL, rank=rank)

    def _farol(self, poi):
        p, cfg = self.progresso, self.chefoes["final"]
        if "final" in p.bosses:
            return self.conversa.iniciar(self._falas(poi["titulo"], [self._texto_farol_aceso()]))
        if not self._todas_concluidas():
            return self.conversa.iniciar(self._falas(poi["titulo"], [self.hist["farol_apagado"]]))
        if self.caca:
            return self.conversa.iniciar(self._falas("A Ressaca", ["Ainda ruge! " + cfg["pistas"][self.caca["i"]]["pista"]]))

        def comecar():
            self.caca = {"i": 0, "restante": float(cfg["tempo"])}
        self.conversa.iniciar(self._falas("A Ressaca", cfg["intro"]), comecar)

    def _avancar_caca(self, pista):
        cfg, p = self.chefoes["final"], self.progresso
        self.caca["i"] += 1
        itens = self._falas("", [pista["ok"]]) if pista["ok"] else []
        if self.caca["i"] >= len(cfg["pistas"]):
            self.caca = None
            p.bosses.add("final")
            p.salvar()
            itens += self._falas("A Ressaca", ["A luz volta ao Farol e a Ressaca recua!"])
            itens += self._falas("Farol de Ponta Negra", [self._texto_farol_aceso()])
        self.conversa.iniciar(itens)

    def _ler_poi(self, poi):
        p = self.progresso
        if self.caca:
            pista = self.chefoes["final"]["pistas"][self.caca["i"]]
            if poi["id"] == pista["alvo"]:
                return self._avancar_caca(pista)
        if poi.get("farol"):
            return self._farol(poi)
        texto = poi["texto"]
        if "fase" in poi and f"boss_{poi['fase']}" in p.bosses:
            texto = poi["texto_ok"]
        if poi.get("curiosidade") and poi["id"] not in p.curiosidades:
            p.curiosidades.add(poi["id"])
            p.salvar()
            texto += "\n(Curiosidade anotada no seu caderno!)"
        self.conversa.iniciar(self._falas(poi["titulo"], [texto]))

    # ---------- atualização e desenho ----------
    def _seguir_jogador(self):
        px, py = self.jogador.posicao_pixels()
        self.camera.seguir(px + TILE / 2, py + TILE / 2)

    def atualizar(self, dt):
        if self.desafio and not self.desafio.ativo:
            self.desafio = None
        self.conversa.atualizar(dt)
        parado = self.conversa.ativa or self.desafio
        if self.caca and not parado:                       # a Ressaca só avança com o jogo livre
            self.caca["restante"] -= dt
            if self.caca["restante"] <= 0:
                self.caca = None
                self.conversa.iniciar(self._falas("A Ressaca", [self.chefoes["final"]["derrota"]]))
        desejada = None if self.conversa.ativa or self.desafio else self.entrada.direcao_atual()
        self.jogador.atualizar(dt, desejada, self.colisao)
        j, p = self.jogador, self.progresso
        cid = self.conchas_mapa.get((j.col, j.linha))
        if cid and not j.andando and cid not in p.conchas_coletadas:
            p.conchas_coletadas.add(cid)
            p.conchas += 1
            p.salvar()
            self.aviso = ("Você achou uma concha! (+1 ajuda)", 2.0)
        self.aviso = (self.aviso[0], max(0.0, self.aviso[1] - dt))
        for n in self.npcs:
            n.tempo_anim += dt
        self._seguir_jogador()

    def _texto(self, tela, txt, pos, fonte=None, cor=(247, 247, 242)):
        fonte = fonte or self.fonte
        tela.blit(fonte.render(txt, True, (0, 0, 0)), (pos[0] + 2, pos[1] + 2))
        tela.blit(fonte.render(txt, True, cor), pos)

    def _zona(self):
        c = self.jogador.col
        return next((z["nome"] for z in self.zonas if z["col_ini"] <= c <= z["col_fim"]), "")

    def _hud(self, tela):
        p = self.progresso
        tela.blit(self.hud_fundo, (10, 10))
        for i, f in enumerate(FASES):
            centro = (30 + i * 28, 33)
            if f"boss_{f}" in p.bosses:
                pygame.draw.circle(tela, OURO, centro, 10)
            pygame.draw.circle(tela, (247, 247, 242), centro, 10, 2)
        self._texto(tela, f"Pontos: {p.placar.total}   Conchas: {p.conchas}", (124, 24))
        self._texto(tela, f"Jogador: {p.nome_jogador} · {self._zona()}", (22, 52), self.fonte_p, OURO)
        self._texto(tela, f"Caderno {len(p.curiosidades)}/{self.total_curiosidades}", (22, 74), self.fonte_p)
        f = self._fase_atual()
        if "final" in p.bosses:
            obj = "Missão cumprida: o Farol está aceso!"
        elif self.caca:
            obj = "Caça ao lugar: siga a pista!"
        elif self._todas_concluidas():
            obj = "Enfrente a Ressaca no Farol!"
        elif p.placar.aprovada(f):
            obj = f"Fase {f}: enfrente o chefão!"
        else:
            obj = f"Fase {f}: guias {p.respondidas(f)}/{PERGUNTAS_POR_FASE}"
        self._texto(tela, obj, (22, 96), self.fonte_p)

    def _hud_caca(self, tela):
        if not self.caca:
            return
        cfg = self.chefoes["final"]
        frac = max(0.0, self.caca["restante"] / cfg["tempo"])
        pygame.draw.rect(tela, (24, 41, 56), (390, 10, 560, 94), border_radius=8)
        pygame.draw.rect(tela, (60, 70, 90), (404, 20, 532, 14))
        pygame.draw.rect(tela, (235, 110, 100) if frac < 0.3 else (80, 160, 220), (404, 20, int(532 * frac), 14))
        self._texto(tela, f"RESSACA  {int(self.caca['restante'])}s", (404, 38), self.fonte_p, OURO)
        for k, linha in enumerate(quebrar(cfg["pistas"][self.caca["i"]]["pista"], self.fonte_p, 530)[:2]):
            self._texto(tela, linha, (404, 60 + k * 20), self.fonte_p)

    def desenhar(self, tela):
        ox, oy = self.camera.x, self.camera.y
        tela.fill(COR_FUNDO)
        tela.blit(self.chao, (-ox, -oy))
        rec = self.jogo.recursos
        for (c, l), cid in self.conchas_mapa.items():     # conchas ainda não coletadas
            if cid not in self.progresso.conchas_coletadas:
                x, y = c * TILE - ox + 32, l * TILE - oy + 40
                pygame.draw.ellipse(tela, (250, 214, 200), (x - 10, y - 7, 20, 14))
                pygame.draw.ellipse(tela, (205, 120, 120), (x - 10, y - 7, 20, 14), 2)
        itens = []
        for o in self.mapa.objetos:
            img = rec.imagem(CATALOGO[o.tipo].arquivo)
            itens.append(((o.linha + 1) * TILE, img,
                          (o.col * TILE - ox, (o.linha + 1) * TILE - img.get_height() - oy)))
        for n in self.npcs:
            tela.blit(self.sombra, (n.col * TILE - ox + 10, n.linha * TILE - oy + TILE - 22))
            itens.append(((n.linha + 1) * TILE, n.quadro(),
                          (n.col * TILE - ox, n.linha * TILE - oy + DESLOC_SPRITE_Y)))
        j = self.jogador
        px, py = j.posicao_pixels()
        sx, sy = round(px) - ox, round(py) - oy
        tela.blit(self.sombra, (sx + 10, sy + TILE - 22))
        if self.bike:
            bike = self.bicicleta.quadro(j.andando, j.tempo_anim, j.direcao)
            if j.direcao in (Direcao.CIMA, Direcao.BAIXO):
                posicao_bike = (sx + (TILE - bike.get_width()) // 2, sy)
            else:
                posicao_bike = (sx, sy + TILE * 3 // 8)
            itens.append((py + TILE, bike, posicao_bike))
        sprite = self.folha.quadro(j.direcao, j.andando, j.tempo_anim)
        itens.append((py + TILE, sprite, (sx, sy + DESLOC_SPRITE_Y)))
        itens.sort(key=lambda i: i[0])
        area = tela.get_rect()
        for _, img, pos in itens:
            if img.get_rect(topleft=pos).colliderect(area):
                tela.blit(img, pos)
        for n in self.npcs:     # "!" em quem ainda tem pergunta para você
            if n.papel == "guia" and not self.progresso.ja_respondeu(n.fase, n.id):
                self._texto(tela, "!", (n.col * TILE - ox + 28, n.linha * TILE - oy - 22), self.fonte, OURO)
        for n in self.npcs:     # chefões ainda não derrotados
            if n.papel == "chefe" and n.id not in self.progresso.bosses:
                self._texto(tela, "CHEFÃO", (n.col * TILE - ox - 4, n.linha * TILE - oy - 22), self.fonte_p, (235, 110, 100))
        self._hud(tela)
        self._hud_caca(tela)
        if self.aviso[1] > 0:
            self._texto(tela, self.aviso[0], (LARGURA // 2 - 150, 130), self.fonte, OURO)
        dica = "WASD andar  E falar  C caderno  B bicicleta " + ("[ligada]" if self.bike else "[desligada]")
        self._texto(tela, dica, (12, ALTURA - 30), self.fonte_p)
        if self.debug:
            self._texto(tela, f"FPS {self.jogo.relogio.get_fps():.0f}  tile ({j.col},{j.linha})  "
                              f"terreno {self.mapa.terreno(j.col, j.linha)}", (12, 118), self.fonte_p)
        if self.desafio and self.desafio.ativo:
            self.desafio.desenhar(tela)
        self.conversa.desenhar(tela)
