"""Ciclo principal do jogo."""
import asyncio

import pygame

from src.core.assets import Recursos
from src.core.config import ALTURA, FPS, LARGURA, TITULO, WEB
from src.scenes.titulo import CenaTitulo
from src.scenes.mundo import CenaMundo


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITULO)
        self.tela = pygame.display.set_mode((LARGURA, ALTURA))
        self.relogio = pygame.time.Clock()
        self.recursos = Recursos()
        self.save_path = None
        self.player_name = ""
        self.musica_ambiente = None
        self.cena = CenaTitulo(self)    # o mundo é criado ao apertar JOGAR
        self.rodando = True

    async def executar(self):
        while self.rodando:
            dt = min(self.relogio.tick(FPS) / 1000, 0.05)   # limita saltos (ex.: janela arrastada)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.rodando = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    if isinstance(self.cena, CenaMundo):
                        # Para a música e retorna ao menu sem apagar o progresso salvo.
                        if self.musica_ambiente:
                            self.musica_ambiente.stop()
                            self.musica_ambiente = None
                        self.cena = CenaTitulo(self)
                    elif not WEB:
                        self.rodando = False
                    else:
                        self.cena.processar_evento(ev)
                else:
                    self.cena.processar_evento(ev)
            self.cena.atualizar(dt)
            self.cena.desenhar(self.tela)
            pygame.display.flip()
            await asyncio.sleep(0)     # necessário para rodar no navegador (Pygbag)
        pygame.quit()
