"""Ambiente sonoro procedural de ondas suaves, sem arquivos externos."""
import math
import random
from array import array

import pygame


def iniciar_ambiente():
    """Toca ondas suaves em loop durante a exploração; falha silenciosamente sem mixer."""
    if not pygame.mixer.get_init():
        return None

    taxa, formato, canais = pygame.mixer.get_init()
    if formato != -16:
        # O jogo usa o formato padrão do Pygame (PCM assinado de 16 bits).
        return None

    duracao = 8
    quantidade = taxa * duracao
    rng = random.Random(23)
    amostras = array("h")
    onda = 0.0
    onda_direita = 0.0

    for i in range(quantidade):
        t = i / taxa
        ruido = rng.uniform(-1.0, 1.0)
        ruido_direito = rng.uniform(-1.0, 1.0)
        # Filtragem simples suaviza o ruído e lembra o vai e vem das ondas.
        onda = onda * 0.985 + ruido * 0.015
        onda_direita = onda_direita * 0.985 + ruido_direito * 0.015
        mare = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.12 * t - 1.2))
        espuma = 0.65 + 0.35 * math.sin(2 * math.pi * 0.31 * t)
        amostras.append(int(max(-1.0, min(1.0, onda * mare * espuma * 12500)))))
        if canais == 2:
            amostras.append(int(max(-1.0, min(1.0, onda_direita * mare * espuma * 12500)))

    som = pygame.mixer.Sound(buffer=amostras.tobytes())
    som.set_volume(0.22)
    som.play(loops=-1)
    return som
