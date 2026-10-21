"""Ambiente sonoro procedural de ondas suaves, sem arquivos externos."""
import math
import random
from array import array

import pygame


def iniciar_ambiente():
    """Toca ondas suaves em loop durante a exploração; falha sem mixer disponível."""
    if not pygame.mixer.get_init():
        return None

    taxa, formato, canais = pygame.mixer.get_init()
    if formato != -16:
        return None

    duracao = 8
    quantidade = taxa * duracao
    rng = random.Random(23)
    amostras = array("h")
    onda_esquerda = 0.0
    onda_direita = 0.0

    for i in range(quantidade):
        t = i / taxa
        onda_esquerda = onda_esquerda * 0.985 + rng.uniform(-1.0, 1.0) * 0.015
        onda_direita = onda_direita * 0.985 + rng.uniform(-1.0, 1.0) * 0.015
        mare = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.12 * t - 1.2))
        espuma = 0.65 + 0.35 * math.sin(2 * math.pi * 0.31 * t)
        esquerda = onda_esquerda * mare * espuma * 35000
        amostras.append(int(max(-32768, min(32767, esquerda))))
        if canais == 2:
            direita = onda_direita * mare * espuma * 12500
            amostras.append(int(max(-32768, min(32767, direita))))

    som = pygame.mixer.Sound(buffer=amostras.tobytes())
    som.set_volume(0.30)
    som.play(loops=-1)
    return som
