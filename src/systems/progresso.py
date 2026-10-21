"""Progresso do jogador: respostas por NPC, placar, curiosidades e save em JSON."""
import json
from pathlib import Path

from src.systems.pontuacao import PERGUNTAS_POR_FASE, TOTAL_FASES, PlacarFases, pontos_da_fase


class Progresso:
    def __init__(self, caminho=None, nome_jogador="Ciclista"):
        self.caminho = caminho
        self.nome_jogador = nome_jogador
        self.placar = PlacarFases()
        self.respostas = {f: {} for f in range(1, TOTAL_FASES + 1)}   # fase -> {npc_id: acertou}
        self.curiosidades = set()
        self.intro_vista = False
        self.tentativas = {}          # npc_id -> quantas vezes já perguntou (gira o banco de perguntas)
        self.conchas = 0              # ajudas disponíveis (H na pergunta elimina uma errada)
        self.conchas_coletadas = set()
        self.bosses = set()           # ids derrotados: boss_1..boss_3 e final

    def respondidas(self, fase):
        return len(self.respostas[fase])

    def ja_respondeu(self, fase, npc_id):
        return npc_id in self.respostas[fase]

    def responder(self, fase, npc_id, acertou):
        """Registra a resposta. Ao fechar as 5 da fase, pontua e devolve o resumo; senão None."""
        self.respostas[fase][npc_id] = bool(acertou)
        self.tentativas[npc_id] = self.tentativas.get(npc_id, 0) + 1
        if len(self.respostas[fase]) < PERGUNTAS_POR_FASE:
            return None
        acertos = sum(self.respostas[fase].values())
        melhorou = self.placar.registrar(fase, acertos)
        return {"acertos": acertos, "pontos": pontos_da_fase(acertos), "melhorou": melhorou,
                "perfeita": acertos == PERGUNTAS_POR_FASE, "aprovada": self.placar.aprovada(fase), "recorde": self.placar.melhor(fase)}

    def reiniciar_fase(self, fase):
        """Nova tentativa: zera as respostas; o recorde e a conclusão continuam."""
        self.respostas[fase] = {}

    def salvar(self):
        if not self.caminho:
            return
        melhores, concluidas = self.placar.dados()
        dados = {"melhores": melhores, "concluidas": concluidas, "intro_vista": self.intro_vista,
                 "respostas": {str(f): r for f, r in self.respostas.items()},
                 "curiosidades": sorted(self.curiosidades), "tentativas": self.tentativas,
                 "bosses": sorted(self.bosses), "conchas": self.conchas, "conchas_coletadas": sorted(self.conchas_coletadas),
                 "nome_jogador": self.nome_jogador}
        try:
            Path(self.caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass    # sem permissão de escrita (ex.: navegador): o jogo segue sem salvar

    def carregar(self):
        if not self.caminho or not Path(self.caminho).exists():
            return
        try:
            d = json.loads(Path(self.caminho).read_text(encoding="utf-8"))
            placar = PlacarFases(d["melhores"], d["concluidas"])
            respostas = {f: {str(k): bool(v) for k, v in d.get("respostas", {}).get(str(f), {}).items()}
                         for f in range(1, TOTAL_FASES + 1)}
            cur, intro = set(d.get("curiosidades", [])), bool(d.get("intro_vista", False))
            tent = {str(k): int(v) for k, v in d.get("tentativas", {}).items()}
            conchas, cols = int(d.get("conchas", 0)), set(d.get("conchas_coletadas", []))
            bosses = set(d.get("bosses", []))
            nome_jogador = str(d.get("nome_jogador", self.nome_jogador))[:18] or "Ciclista"
        except (ValueError, KeyError, TypeError, AttributeError):
            return   # save corrompido: começa do zero
        self.placar, self.respostas, self.curiosidades, self.intro_vista = placar, respostas, cur, intro
        self.tentativas, self.conchas, self.conchas_coletadas, self.bosses = tent, conchas, cols, bosses
        self.nome_jogador = nome_jogador
