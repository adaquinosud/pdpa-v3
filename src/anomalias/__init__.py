"""Motor de Monitoramento ML (Bloco 8) — anomalias híbridas v3.

Camada 1 (``camada1``): anomalia em indicadores agregados (ratio P/D por
loja×subpilar), portada do pdpa-v2 — cross-sectional z-robusto (mediana+MAD,
cauda inferior) + temporal (IsolationForest sklearn, no lugar do Merlion).
Camada 2 (temas/cruzamentos), combinação e editorial chegam nos CPs seguintes.

Série temporal vem de ``ratios_mensais`` (``ratios.recomputar_ratios_mensais``),
construída sobre o histórico COMPLETO da empresa (não a janela 180d — essa é
só para temas).
"""
