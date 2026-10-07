# Veo 3.1 — "Quatro Regras, Um Gol"

Pacote completo de prompts para gerar um vídeo de 12 segundos explicando as regras básicas do futebol com o Google Veo 3.1. Prompts em inglês (o modelo responde melhor), narração em português do Brasil.

## Comece aqui (5 passos)

1. **Flow** → novo projeto → *Text to Video* → **Veo 3.1 – Quality** → 16:9 → **720p** → 4 saídas → colar o **Prompt A** (seção 2) → gerar.
2. Aprovar **1 take** pela checklist da seção 5 (luvas, geometria do impedimento, cartão amarelo, zero texto, uma bola, ninguém mexe a boca).
3. **Rota A:** *Extend* no take aprovado com o **Prompt B** (seção 3) → 2 a 4 saídas. Se falhar 2x: **Rota B** = *Text to Video* de **6 s** em 720p com o **Prompt C** (seção 3) e emenda em pós.
4. Montar **12,00 s** (seção 9): corte seco no rugido, **sem fade** no "Goooool!"; se o gol entrar tarde, apagar os frames congelados da junção.
5. Exportar com **upscale 4K**, aplicar os **rótulos em pós** (seção 5) e arquivar a versão limpa.

---

## 1. Conceito em uma frase

**Um filme esportivo noturno de 12 s em que cada regra é um objeto-ícone em ação (luvas que fecham na bola, bandeira que sobe, cartão amarelo, bola cruzando a linha do gol), montado em quatro lances da mesma partida com um protagonista — o atacante azul é flagrado impedido, depois sofre a falta imprudente na área e converte o pênalti — narrado em pergunta-resposta por um locutor brasileiro, com o "Goooool!" arrastado fechando o vídeo entre 10,7 e 12,0 s.**

Regras escolhidas (e por quê):

| # | Regra | Como aparece | Por que entrou |
|---|---|---|---|
| 1 | Só o goleiro pode segurar a bola com as mãos — e só dentro da própria área (fora do vídeo: arremesso lateral, toque acidental, recuo de pé do companheiro) | Goleiro de laranja já no ar, dentro da área, gol e rede atrás dele; linha da área entre a câmera e ele | Ícone mais reconhecível do futebol; uma ação, um sujeito |
| 2 | Impedimento: posição julgada **no momento do passe** | Pé do passador acabou de tocar a bola na borda esquerda; bola no ar; atacante dois passos além do último defensor; goleiro ao fundo; bandeira sobe | A regra que o leigo mais quer entender; legível no mudo com a geometria em foco profundo |
| 3 | Falta imprudente (atrasada, pelo lado, sem bola) → cartão amarelo; como foi dentro da área → pênalti | Carrinho atrasado pelo lado pega o tornozelo; apito único; cartão erguido e segurado; árbitro aponta a marca | Causa e efeito visíveis; "imprudente" é o termo da Regra 12 (força excessiva seria vermelho) |
| 4 | Gol: **a bola inteira** cruza a linha | Câmera deitada na linha do gol; bola cruza inteira a 1 m da lente com grama visível entre bola e linha; rede estufa | Clímax; o ângulo prova a regra sem texto; pênalti é a física mais simples para o modelo |

Fora: 11 x 11, 2 x 45, lateral/escanteio — exigem números/texto ou são pouco dramáticos; não cabem sem confundir.

---

## 2. Prompt principal — Clipe 1 (8 s, Veo 3.1) — "Prompt A"

Cole exatamente assim (inglês; falas em PT-BR entre aspas). Três planos: **2 s + 3 s + 3 s**, cada um com uma câmera, um sujeito principal e um único "hold" (fim do plano 3, ponto de corte). 522 palavras. Proporção, duração e resolução vão só nos parâmetros.

```text
Cinematic night football film: shallow depth of field, anamorphic flares, light 35mm grain, high contrast, hard white floodlights as backlight, thin haze, wet glistening pitch. The orange jersey, the checkered flag and the yellow card are the only warm colors. Packed stadium, the stands an out-of-focus wall of fans and bokeh with no screens or banners, unlit black perimeter boards, crisp white lines, nothing drawn over the picture. Three shots joined by hard cuts. Voice-over narration only; nobody on screen speaks.

CAST, plain blank kits, no crests, sponsors or numbers. GOALKEEPER: lean, light-brown skin, shaved head, bright orange long-sleeve jersey, black shorts, black gloves. BLUE TEAM: royal-blue shirts, shorts and socks; their STRIKER: athletic Brazilian man, dark-brown skin, short black curly hair, short beard. WHITE TEAM: white shirts, black shorts and socks. REFEREE: short grey hair, all black. One single white ball with black panels.

[00:00-00:02] Low angle at grass level just outside the penalty area, looking into the box toward the goal, slow push-in, slow motion. The orange goalkeeper, well inside his area with the goal and net directly behind him, is already airborne mid-dive on the first frame; the ball thumps into both gloves and stops dead, water spraying, and he pulls it to his chest as he lands. The white penalty-area line crosses the foreground between camera and goalkeeper. SFX: a dry crack on the first frame, a deep thump in the gloves; the crowd gasps. The commentator says in Brazilian Portuguese, "Mão? Só o goleiro, na área."

[00:02-00:05] Hard cut to: elevated static camera on the touchline, level with the last white defender, deep focus in this shot, slow motion. At the center of the frame the blue striker is two full steps closer to the goal (frame right) than the last white defender. At the left edge a blue teammate has just kicked the ball; the ball flies slowly between them at head height toward the striker. The orange goalkeeper stands small on his goal line at the far right. In the left mid-ground a female assistant referee in black snaps an orange-and-yellow checkered flag straight up. SFX: the thud of the pass, the flag snapping, a crowd groan. The commentator says in Brazilian Portuguese, "Além do último defensor? Impedimento."

[00:05-00:08] Hard cut to: static low camera at grass height inside the penalty area, real-time speed, the white penalty-area line in the foreground. A white defender slides in late from the side, misses the ball and catches the blue striker's ankle with his trailing leg; the striker tumbles and stays down. The referee steps into the foreground, blows his whistle once and raises a bright yellow card high, then stands perfectly still with the card raised for the entire last second, the striker on the grass behind him. SFX: boots sliding on wet grass, one sharp whistle, loud boos. The commentator says in Brazilian Portuguese, "Falta imprudente? Amarelo."

AUDIO: deep, warm male Brazilian football commentator voice, clean full-range studio recording, unhurried, one short line per shot with silence between lines, clearly louder than the crowd. Ambient noise: packed stadium crowd, distant batucada drums, stadium echo. No music.
```

Regras de escrita aplicadas: aspas só nas falas do locutor (reações da torcida sem aspas); nenhuma nota para humanos dentro do prompt; nenhum timestamp dentro de segmento; "Hard cut to:" abre os planos 2 e 3; "rádio" aparece só no "Goooool!" da parte 2.

---

## 3. Prompt da extensão — segundos 8 a 12

### As duas rotas e qual usar

| | Rota A — **Extend** (principal) | Rota B — clipe 2 de **6 s, text-to-video** (reserva) |
|---|---|---|
| Como | Extend sobre o clipe 1 (Flow ou API): +7 s a partir do último ~1 s de contexto; total ~15 s; **cortar em 12,00 s** | Gerar um clipe de 6 s **sem first frame**, começando direto no pênalti; emendar em 8,0 s; usar ~4 s dele (os 2 s finais são hold na rede = folga de edição) |
| Resolução | Clipe 1 e Extend em **720p** (a API só estende 720p e o Extend do Flow devolve 720p — **conferir na doc vigente**) → upscale 4K na exportação | **Mesma resolução do clipe 1** (720p se o clipe 1 foi feito para a Rota A); 1080p+1080p só se o Extend já estava descartado antes de gerar o clipe 1 (ex.: Gemini app). **Nunca misturar 720p e 1080p nas duas metades** |
| Continuidade | O whip pan parte do frame parado do árbitro, usando o ~1 s de contexto a favor | Bloco CAST idêntico + Ingredients (stills do atacante e do goleiro extraídos do clipe 1) + seed do take aprovado (API/Vertex); a junção é um corte seco, então não há exigência de continuidade de frame |
| Vantagem | **Tende a** manter timbre do narrador, cama de torcida, luz e uniformes (gerar 2–4 e escolher pelo ouvido; VO em pós como reserva) | Mais controle sobre o lance do gol; sem risco de "foto parada"; folga de 2 s |
| Risco | Pode ficar >1 s no árbitro antes do whip; o corte real cai entre 8,0 e 9,0 s (corrigível em pós apagando frames congelados) | Timbre da voz e cama sonora podem mudar na emenda (fade de 0,2 s; VO única em pós se divergir) |
| Use quando | Sempre que o Extend estiver disponível (Flow/API) | Extend indisponível, ou o Extend falhou 2 vezes em sair do plano do cartão |

Nas duas rotas a junção em 8,0 s acontece sobre o **frame segurado do cartão** (último segundo do clipe 1). Corte em frame parado, nunca no meio de uma ação.

### ROTA A — prompt de Extend (+7 s, cortar em 12,00 s) — "Prompt B"

456 palavras. A operação Extend é escolhida na interface/API, não no texto. Prosa sequencial (timestamps são pouco confiáveis no Extend).

```text
Continue the same film with no change of look: the same packed night stadium under hard white floodlights, thin haze, wet glistening pitch, anamorphic flares, light 35mm grain, high contrast, nothing drawn over the picture. Same cast in the same plain blank kits, no crests, sponsors or numbers: the BLUE STRIKER (athletic Brazilian man, dark-brown skin, short black curly hair, short beard, royal-blue shirt, shorts and socks), the orange GOALKEEPER (lean, light-brown skin, shaved head, bright orange long-sleeve jersey, black shorts, black gloves), the REFEREE (short grey hair, all black). One single white ball with black panels. Voice-over narration only; nobody on screen speaks.

The referee lowers the yellow card and points one straight arm at the penalty mark; the camera whip-pans right, the only camera move of this shot, and lands on a wide low static view from behind and slightly beside the blue striker, real-time speed: he is already two strides into his run-up to the ball on the penalty mark, every other player outside the penalty area, the orange goalkeeper on his goal line far ahead, the stands behind the goal a blurred wall of fans; he drives the ball low and hard toward the bottom-left corner and the goalkeeper dives the wrong way, toward the far post. The referee and the yellow card are not seen again. Hard cut to a static goal-line camera lying on the goal line just inside the left post at grass level, looking along the white line toward the far post, super slow motion: the ball flies in low and crosses completely over the white line one meter from the lens; for a moment the whole ball is visibly past the line with grass between ball and line, then it hits the net; the net bulges and ripples; the goalkeeper lands on the grass in the background. The camera stays on the ball resting inside the net, the white line sharp in the foreground, the floodlit crowd blurred behind, for the rest of the clip while the crowd keeps roaring.

AUDIO: the same deep, warm male Brazilian football commentator voice, clean full-range studio recording, clearly louder than the crowd, continues in Brazilian Portuguese: "Pênalti!" as the referee points at the mark; "Passou inteira?" as the ball crosses the line in slow motion; then a long, drawn-out radio-style "Goooool!" that starts the instant the ball is fully over the line and keeps going to the end of the clip. SFX: one short referee whistle during the whip pan, running steps, the dry crack of the strike, the ball hissing, the whip of the net, then fifty thousand fans roaring with pounding batucada drums. Ambient noise: the crowd hushes for one beat under the run-up, then explodes. No music.
```

Pós (Rota A): o whip pan deve começar entre 8,0 e 9,0 s. Se começar depois de 8,0 s, **apague os frames entre 8,0 s e o primeiro frame de movimento** (o cartão está parado dos dois lados; a emenda é invisível com crossfade de áudio de 0,1 s) — isso traz a bola inteira dentro da linha para ≤ 10,8 s. Corte final em **12,00 s** sobre a bola parada na rede, **sem fade** no "Goooool!". Os segundos 12–15 são descarte.

### ROTA B — clipe 2 de 6 s (text-to-video, sem first frame) — "Prompt C"

465 palavras. Três segmentos; o terceiro é zona de corte.

```text
Cinematic night football film: shallow depth of field, anamorphic flares, light 35mm grain, high contrast, hard white floodlights as backlight, thin haze, wet glistening pitch. Packed stadium, the stands an out-of-focus wall of fans and bokeh with no screens or banners, unlit black perimeter boards, crisp white lines, nothing drawn over the picture. Two shots joined by a hard cut. Voice-over narration only; nobody on screen speaks.

CAST, plain blank kits, no crests, sponsors or numbers. BLUE STRIKER: athletic Brazilian man, dark-brown skin, short black curly hair, short beard, royal-blue shirt, shorts and socks. GOALKEEPER: lean, light-brown skin, shaved head, bright orange long-sleeve jersey, black shorts, black gloves. REFEREE: short grey hair, all black. One single white ball with black panels.

[00:00-00:02] Wide low static camera from behind and slightly beside the blue striker, real-time speed. At the right edge of the frame the referee points one straight arm at the penalty mark. The striker is already two strides into his run-up to the ball on the penalty mark, every other player outside the penalty area, the orange goalkeeper on his goal line far ahead, the stands behind the goal a blurred wall of fans; he drives the ball low and hard toward the bottom-left corner and the goalkeeper dives the wrong way, toward the far post. SFX: one short referee whistle on the very first frame, running steps, the dry crack of the strike. The commentator says in Brazilian Portuguese, "Pênalti!" over the run-up.

[00:02-00:04] Hard cut to: static goal-line camera lying on the goal line just inside the left post at grass level, looking along the white line toward the far post, super slow motion. The ball flies in low and crosses completely over the white line one meter from the lens; for a moment the whole ball is visibly past the line with grass between ball and line, then it hits the net; the net bulges and ripples; the goalkeeper lands on the grass in the background. SFX: the ball hissing, the whip of the net, then fifty thousand fans roaring with pounding batucada drums. The commentator says in Brazilian Portuguese, "Passou inteira?" as the ball crosses the line, then a long, drawn-out radio-style "Goooool!" that starts the instant the ball is fully over the line and keeps going to the end of the clip.

[00:04-00:06] Same camera, no cut: the ball rests inside the net, the net sways and settles, the white line sharp in the foreground, the floodlit crowd blurred behind; the crowd keeps roaring and the commentator's "Goooool!" continues.

AUDIO: deep, warm male Brazilian football commentator voice, clean full-range studio recording, unhurried, clearly louder than the crowd. Ambient noise: a packed stadium crowd, hushed for one beat under the run-up, then an explosive roar with batucada drums. No music.
```

**Variante para superfícies travadas em 8 s (Gemini app):** substitua o segmento `[00:04-00:06]` pela linha abaixo e mantenha todo o resto. Em pós, use só os ~4 primeiros segundos.

```text
[00:04-00:08] Same camera, no cut: the ball rests inside the net, the net sways and settles, the white line sharp in the foreground, the floodlit crowd blurred behind; the crowd keeps roaring and the commentator's "Goooool!" continues.
```

Pós (Rota B): emendar em 8,0 s com fade de áudio de 0,2 s em cada lado da junção; aparar o início do clipe 2 se houver frames de "acomodação" antes da corrida; total exato de 12,00 s. Gerar 4 amostras e escolher a de timbre mais próximo do clipe 1; se a voz divergir, locução única em pós mantendo SFX/torcida do Veo.

---

## 4. Negative prompt

Usar no campo `negativePrompt` (API Gemini/Vertex). No Flow não há campo próprio: as exclusões já estão escritas positivamente nos prompts ("plain blank kits", "unlit black perimeter boards", "no screens or banners", "nothing drawn over the picture"). Itens curtos, sem frases condicionais; sem "blurry" (contradiz a profundidade de campo rasa e o bokeh) e sem "rain" (contradiz o gramado molhado e a água nas luvas).

Base (clipe 1 e parte 2):

```text
text, captions, subtitles, scoreboard, stadium screen, jumbotron, broadcast graphics, lower thirds, VAR graphics, replay wipe, logos, watermarks, club crests, sponsor logos, brand names, advertising boards, banners, fan signs, flags with text, shirt numbers, real players, celebrity faces, extra ball, duplicated ball, deformed hands, extra fingers, deformed feet, warped limbs, kit color change, face change, morphing, lip-sync, talking faces, red card, cartoon, anime, low quality, daytime, empty stadium
```

Acréscimo só na parte 2 (Extend e Prompt C):

```text
, crowd of players inside the penalty area, defensive wall, second ball
```

---

## 5. Configurações recomendadas

| Parâmetro | Valor |
|---|---|
| Modelo | **Veo 3.1 Quality** (Flow: "Veo 3.1 – Quality"; API: `veo-3.1-generate-preview`, conferir o ID vigente). Fast (`veo-3.1-fast-generate-preview`) só para validar blocking antes de gastar créditos |
| Proporção | 16:9 (master). 9:16 = regerar com a variante da seção 8, nunca recortar |
| Resolução | **Clipe 1 sempre em 720p** (serve às duas rotas). Rota A: Extend em 720p. Rota B: clipe 2 na mesma resolução do clipe 1. Upscale 4K do master final na exportação do Flow (nas duas rotas). 1080p+1080p só quando o Extend já está descartado antes de gerar o clipe 1 (1080p pode exigir 16:9 e/ou 8 s — conferir) |
| Áudio | Sempre nativo (fala PT-BR, SFX, ambiente). Vertex: `generateAudio: true` |
| Duração | Clipe 1: 8 s. Rota A: Extend +7 s, corte em 12,00 s. Rota B: 6 s (ou 8 s cortado em ~4 s em superfícies fixas em 8 s) |
| Nº de gerações | Clipe 1: 4 amostras. Extend: 2 a 4. Clipe 2 (Rota B): 4. Escolher o take antes de estender/emendar |
| Seleção do take (clipe 1) | Aprovar só se: (1) bola apoiada no peito do goleiro, **linha da área à frente dele e gol/rede atrás**; (2) perna do passador na borda esquerda, bola no ar, atacante claramente dois passos além do último defensor, goleiro atrás, bandeira erguida; (3) cartão nitidamente amarelo, erguido e parado no último segundo; (4) zero texto/placar/número/escudo/telão; (5) nenhum rosto parecido com atleta real; (6) uma só bola; (7) ninguém mexe os lábios com a narração |
| Seleção do take (parte 2) | Descartar se: fica > 1 s no árbitro antes do whip pan (Rota A); mais de um apito; bola cruza longe da lente ou goleiro cai por cima da linha em primeiro plano; "Goooool!" antes de a bola cruzar; mudança de rosto/uniforme; texto |
| seed | Explore **sem seed fixa** (ou seeds diferentes) até aprovar o take; anote a seed do take aprovado e reutilize-a **só na parte 2** e nas regerações da parte 2. Flow não expõe seed: use 4 saídas. Identidade entre as partes vem do CAST, do Extend/Ingredients — não da seed |
| personGeneration | `allow_all` em text-to-video (API Gemini; indisponível em EU/UK/MENA — omitir); `allow_adult` em image-to-video. Conferir |
| enhancePrompt (Vertex) | `false` se o modelo permitir (nos Veo 3.x pode ser fixo em `true` — conferir); por isso os prompts já evitam qualquer pedido de texto/placar |
| negativePrompt | Campo próprio com a lista da seção 4 |
| Pós | Corte em 12,00 s; -14 LUFS / TP -1; **sem fade** no fim (corte seco no rugido); rótulos em pós conforme abaixo; versão limpa arquivada |

### Parâmetro × superfície (conferir nomes e limites na doc vigente antes de gastar créditos)

| Parâmetro | Gemini API (`google-genai`) | Vertex AI | Flow |
|---|---|---|---|
| Modelo | `veo-3.1-generate-preview` / `veo-3.1-fast-generate-preview` | ID equivalente (conferir) | Veo 3.1 – Quality / Fast |
| Duração | `duration_seconds` 4/6/8 | `durationSeconds` 4/6/8 | 4/6/8; Extend +7 |
| Resolução | `resolution` 720p/1080p | `resolution` | 720p/1080p; upscale 4K na exportação |
| Proporção | `aspect_ratio` 16:9 / 9:16 | `aspectRatio` | 16:9 / 9:16 |
| Áudio | sempre gerado | `generateAudio: true` | sempre |
| Negativo | `negative_prompt` | `negativePrompt` | não há campo (exclusões positivas no texto) |
| Pessoas | `person_generation` `allow_all` (texto) / `allow_adult` (imagem) | `personGeneration` | — |
| Nº de saídas | `number_of_videos` (limite da API: conferir) | `sampleCount` até 4 | até 4 |
| Seed | pode ser ignorada (conferir) | `seed` | não há |
| enhancePrompt | — | `enhancePrompt` (pode ser fixo) | — |
| Extend | `video=<objeto gerado pelo Veo 3.1>`, 720p, +7 s (não aceita upload) | idem | *Extend* no take |
| Ingredients / frames | `reference_images` / `image` / `last_frame` (conferir) | `referenceImages` / `image` / `lastFrame` | *Ingredients* / *Frames to Video* |

### Texto em pós (obrigatório no 9:16; recomendado no 16:9 para redes; nunca pedido ao Veo)

Sans bold, caixa alta, branco com sombra leve, terço superior, fora das áreas de UI do Reels/TikTok, entrada sincronizada com a pergunta do locutor, fade de 4 frames, sem animação. Cada rótulo dura o plano correspondente. Entregar também a versão limpa (sem texto) para TV/telão.

| Tempo | Rótulo | Cai sobre |
|---|---|---|
| 0,0–0,8 s | 4 REGRAS EM 12 SEGUNDOS (só social/9:16) | Primeiro frame (estalo do chute) |
| 0,8–2,0 s | MÃO? SÓ O GOLEIRO | Bola no peito do goleiro |
| 3,8–5,0 s | IMPEDIMENTO | Bandeira erguida |
| 6,8–8,0 s | AMARELO | Cartão erguido e parado |
| 8,2–9,6 s | NA ÁREA? PÊNALTI | Árbitro apontando a marca / corrida |
| 10,8–12,0 s | GOL! | Rede estufando |

---

## 6. Roteiro de narração (PT-BR)

Voz: locutor brasileiro de futebol, masculina, grave e quente, **gravação de estúdio limpa e de banda cheia** (não filtrada como rádio AM), sem pressa, em off (sem lip-sync), uma linha curta por plano com silêncio entre as linhas, acima da torcida na mixagem. "Estilo rádio" só no "Goooool!" arrastado. Formato pergunta-resposta. Limite adotado: **≤ 5 sílabas/s** (mais restritivo que o teto de ~2,8 palavras/s). As janelas são alvo de seleção de take (o Veo não aceita marcação de 0,1 s) e guia para a VO em pós se a voz divergir.

**Clipe 1 (8 s, limite ~18 palavras) — 14 palavras, 34 sílabas**

| Tempo | Fala | Palavras | Sílabas | Síl/s | Cai sobre |
|---|---|---|---|---|---|
| 0,3–2,2 s | "Mão? Só o goleiro, na área." | 6 | 10 | 5,0 | Luvas fechando na bola (pode vazar 0,2 s sobre o corte) |
| 2,3–5,0 s | "Além do último defensor? Impedimento." | 5 | 14 | 5,2 | "Impedimento" cai na bandeira (3,8–5,0 s) |
| 5,6–7,4 s | "Falta imprudente? Amarelo." | 3 | 10 | 5,0 | "Amarelo" cai no cartão (6,8 s); 7,4–8,0 só vaias |

**Parte 2 (4 s úteis, limite ~10 palavras) — 4 palavras**

| Tempo | Fala | Palavras | Sílabas | Cai sobre |
|---|---|---|---|---|
| 8,2–8,7 s | "Pênalti!" | 1 | 3 | Árbitro apontando a marca / início da corrida |
| 9,8–10,6 s | "Passou inteira?" | 2 | 5 | Bola cruzando a linha em super câmera lenta |
| 10,7–12,0 s | "Goooool!" (arrastado, ≥ 1,2 s, sem fade) | 1 | — | Bola inteira dentro da linha → rede estufando → corte seco |

**Total: 18 palavras em 12 s (~1,5 palavras/s)** — folga para o estalo do chute, o apito único, o hush de um tempo antes da cobrança e a explosão da torcida. O "Goooool!" nunca dispara antes de a bola estar inteira dentro da linha.

Se algum dia gerar em inglês (trocar "says in Brazilian Portuguese" por "says in English"): "Handball? Only the keeper, in his box." / "Past the last defender? Offside." / "Reckless foul? Yellow." / "Penalty!" / "All the way over?" / "Goooal!" — mesmos tempos.

---

## 7. Shot list segundo a segundo (fonte única de verdade)

Os prompts das seções 2 e 3 e as tabelas da seção 6 derivam desta tabela.

| Tempo | Câmera (1 movimento) | Ação | Áudio / Narração | Regra |
|---|---|---|---|---|
| 0,0–2,0 s | P1: ângulo baixo rente à grama **logo fora da área**, olhando para dentro da área e para o gol; push-in lento; câmera lenta | Goleiro laranja **já no ar**, dentro da área, gol e rede atrás dele; bola estala nas luvas e para, água voando; abraça no peito ao cair; linha da área em primeiro plano entre câmera e goleiro | Estalo seco no frame 0 (gancho), baque nas luvas, suspiro. "Mão? Só o goleiro, na área." | Mãos: só o goleiro, na própria área |
| 2,0–5,0 s | P2: corte seco; **lateral elevada da linha LATERAL (touchline)**, alinhada ao último defensor; estática; foco profundo; câmera lenta | Companheiro azul acabou de chutar (borda esquerda); bola no ar na altura da cabeça indo para o atacante; atacante **dois passos** além do último defensor; goleiro pequeno na linha do gol à direita; assistente no meio-campo esquerdo ergue a bandeira | Baque do passe, estalo da bandeira, suspiro da torcida. "Além do último defensor? Impedimento." | Impedimento no momento do passe |
| 5,0–8,0 s | P3: corte seco; câmera baixa **estática** rente à grama dentro da área; tempo real | Carrinho **atrasado pelo lado** pega o tornozelo com a perna de trás; atacante cai e fica; árbitro entra no primeiro plano, **apita uma vez**, ergue o amarelo; **7,0–8,0 s parado com o cartão erguido** (ponto de corte) | Chuteiras deslizando, apito, vaias. "Falta imprudente? Amarelo." | Falta imprudente → amarelo |
| 8,0–9,6 s | P4: Rota A — árbitro abaixa o cartão e **aponta a marca**, whip pan à direita (único movimento) que pousa num plano baixo estático atrás do atacante; Rota B — mesmo plano, estático, árbitro apontando na borda direita; tempo real | Apito único (durante o whip / no 1º frame); atacante **já em corrida**; demais jogadores fora da área; chute rasteiro no **canto esquerdo baixo**; goleiro cai para o lado errado (poste distante) | Apito, hush de um tempo, passos, estalo seco do chute. "Pênalti!" | Falta na área → pênalti |
| 9,6–11,0 s | P5: corte seco; câmera **deitada na linha do gol junto ao poste esquerdo**, olhando ao longo da linha; estática; super câmera lenta | Bola entra baixa, **cruza inteira a linha a 1 m da lente**, grama visível entre bola e linha (~10,6 s), bate na rede (~10,8 s); goleiro cai ao fundo | Bola cortando o ar. "Passou inteira?" (9,8–10,6) | Gol: a bola inteira cruza a linha |
| 11,0–12,0 s | P5, hold (sem corte) | Rede estufa e ondula; **bola parada na rede, linha em foco**; torcida explode | Chicote da rede, explosão com batucada. "Goooool!" (10,7 → 12,0, corte seco no auge) | Clímax / ponto de corte |
| 12–15 s | (só no Extend; descarte) hold contínuo na rede | — | Rugido contínuo | Zona de corte segura |

---

## 8. Variante 9:16 (Reels/TikTok/Shorts)

Regerar tudo em 9:16 com os mesmos prompts e apenas estas trocas (não recortar o 16:9). Mesma lateralidade (canto esquerdo baixo, câmera junto ao poste esquerdo).

- **Cabeçalho (Prompts A e C):** trocar `Three shots joined by hard cuts.` / `Two shots joined by a hard cut.` por `Vertical framing, subjects centered, tighter framing except the offside shot, which stays wide. Three shots joined by hard cuts.` (ou `Two shots...`). O parâmetro `aspectRatio` vai em `9:16`.
- **Plano 1:** acrescentar após "slow motion.": `The goalkeeper centered, filling the height of the frame, the goal frame behind him, the penalty-area line along the bottom of the frame.`
- **Plano 2 (impedimento):** substituir a câmera e o posicionamento por: `Hard cut to: elevated static camera high behind the goal, above the crossbar, looking down the pitch, deep focus in this shot, slow motion. The orange goalkeeper at the bottom of the frame; the blue striker a clear two steps lower in the frame (closer to the goal) than the last white defender; a blue teammate at the top of the frame has just kicked the ball; the ball flies slowly between them. At the left edge a female assistant referee in black snaps an orange-and-yellow checkered flag straight up.` (a linha de impedimento vira horizontal na tela.) Manter SFX e fala.
- **Plano 3:** acrescentar: `The referee centered, the yellow card raised toward the top of the frame.`
- **Extend / Prompt C — plano do pênalti:** `from directly behind the striker, the striker at the bottom of the frame, the goal at the top`.
- **Extend / Prompt C — câmera da linha do gol:** `the white line running from the bottom to the top of the frame, the ball crossing it one meter from the lens`.
- **Pós:** rótulos da seção 5 são obrigatórios (autoplay sem som), dentro da safe area.

---

## 9. Como gerar passo a passo

**Passo 0 — Validação barata (Fast).** Rode o Prompt A no Veo 3.1 Fast (2 amostras) só para conferir blocking, cores e se os 3 planos saem na ordem. Não use o resultado; ajuste e passe ao Quality.

**Passo 0,5 — Decida a resolução antes do clipe 1.** Flow/API com Extend disponível → 720p em tudo + upscale 4K. Extend descartado de antemão (Gemini app) → a resolução que a superfície entregar, igual nas duas partes.

**Flow (recomendado)**
1. Novo projeto → *Text to Video* → Veo 3.1 – Quality → 16:9 → 720p → 4 saídas → cole o **Prompt A** → gerar.
2. Selecione o take com a checklist da seção 5 (tela cheia; confira linha à frente/gol atrás no plano 1, dois passos no plano 2, cartão amarelo parado, bola única, ausência de texto).
3. **Rota A:** no take escolhido → *Extend* → cole o **Prompt B** → 2 a 4 saídas → escolha pela checklist da parte 2 → *Add to scene builder* → apague frames congelados da junção se o whip pan começar depois de 8,0 s → corte em 12,00 s → exportar com **upscale 4K**.
4. **Rota B:** baixe o clipe 1 → extraia `gk.png` e `striker.png` (comandos abaixo) → *Text to Video* (ou *Ingredients to Video* com os dois stills) → 6 s → 720p → cole o **Prompt C** → 4 saídas → escolha a de timbre mais próximo → emende com o comando abaixo → upscale 4K na exportação.

**Gemini app**
Só texto→vídeo e imagem→vídeo de 8 s, sem Extend, sem negative prompt e sem seed. Use a **Rota B**: gere o clipe 1 com o Prompt A; gere o clipe 2 com o Prompt C na **variante 8 s** (seção 3); use só os ~4 primeiros segundos do clipe 2; emende em pós. Para controle total, prefira Flow ou API.

**API Gemini (Python; conferir nomes de parâmetros e limites na doc vigente)**
```python
# Conferir na doc vigente: IDs de modelo, limites de number_of_videos, valores de person_generation,
# restrições de 1080p e se o Extend exige 720p. Vertex: usar seed, generateAudio=True, enhancePrompt.
from google import genai
from google.genai import types
import time

client = genai.Client()  # GEMINI_API_KEY no ambiente

def wait(op):
    while not op.done:
        time.sleep(10)
        op = client.operations.get(op)
    return op

MODEL = "veo-3.1-generate-preview"  # Fast: "veo-3.1-fast-generate-preview" (só para validar blocking)
base = dict(aspect_ratio="16:9", negative_prompt=NEGATIVE, number_of_videos=2)  # limite da API: conferir

# Clipe 1 — SEMPRE 720p (serve às Rotas A e B). person_generation="allow_all" é o valor de text-to-video
# (indisponível em EU/UK/MENA: omitir o parâmetro).
op = wait(client.models.generate_videos(
    model=MODEL, prompt=PROMPT_A,
    config=types.GenerateVideosConfig(resolution="720p", duration_seconds=8,
                                      person_generation="allow_all", **base)))
clip1 = op.response.generated_videos[0].video      # troque o índice pelo take aprovado
client.files.download(file=clip1); clip1.save("clip1.mp4")

# Rota A — Extend (+7 s). Só aceita o objeto de vídeo gerado pelo Veo 3.1, em 720p.
op = wait(client.models.generate_videos(
    model=MODEL, prompt=PROMPT_B, video=clip1,
    config=types.GenerateVideosConfig(resolution="720p", **base)))
ext = op.response.generated_videos[0].video
client.files.download(file=ext); ext.save("extend.mp4")

# Rota B — clipe 2 de 6 s, text-to-video, MESMA resolução do clipe 1.
op = wait(client.models.generate_videos(
    model=MODEL, prompt=PROMPT_C,
    config=types.GenerateVideosConfig(resolution="720p", duration_seconds=6,
                                      person_generation="allow_all", **base)))
clip2 = op.response.generated_videos[0].video
client.files.download(file=clip2); clip2.save("clip2.mp4")
```

**Pós-produção (ffmpeg)**
```bash
# Stills de identidade para Ingredients (Rota B) — último frame real e dois rostos
ffmpeg -sseof -0.05 -i clip1.mp4 -update 1 -frames:v 1 -q:v 1 last.png
ffmpeg -ss 1.6 -i clip1.mp4 -frames:v 1 -q:v 1 gk.png
ffmpeg -ss 5.2 -i clip1.mp4 -frames:v 1 -q:v 1 striker.png

# Rota A (whip pan começou em 8,0 s): cortar em 12,00 s, SEM fade no grito, loudness -14 LUFS
ffmpeg -i extend.mp4 -t 12 -af "loudnorm=I=-14:TP=-1:LRA=11" -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -c:a aac -b:a 320k final_12s.mp4

# Rota A (whip pan começou depois de 8,0 s, ex.: 8,6 s): apagar os frames congelados entre 8,0 s e o primeiro frame de movimento (M)
M=8.6
ffmpeg -t 8 -i extend.mp4 -ss $M -i extend.mp4 -filter_complex "[0:a]afade=t=out:st=7.9:d=0.1[a0];[1:a]afade=t=in:st=0:d=0.1[a1];[0:v][a0][1:v][a1]concat=n=2:v=1:a=1[v][a];[a]loudnorm=I=-14:TP=-1:LRA=11[aout]" -map "[v]" -map "[aout]" -t 12 -c:v libx264 -crf 16 -preset slow -pix_fmt yuv420p -c:a aac -b:a 320k final_12s.mp4

# Rota B: emendar 8 s + ~4 s do clipe 2 com guarda de escala/fps (use a resolução do clipe 1: 1280:720 ou 1920:1080),
# fade de 0,2 s em cada lado da junção. Ajuste -ss/-t ao take (a soma deve dar 12,0; se aparar o início do clipe 1, st = duração do trecho - 0,2).
ffmpeg -ss 0 -t 8 -i clip1.mp4 -ss 0.2 -t 4.0 -i clip2.mp4 -filter_complex "[0:v]scale=1280:720:flags=lanczos,fps=24,format=yuv420p[v0];[1:v]scale=1280:720:flags=lanczos,fps=24,format=yuv420p[v1];[0:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=out:st=7.8:d=0.2[a0];[1:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:st=0:d=0.2[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a];[a]loudnorm=I=-14:TP=-1:LRA=11[aout]" -map "[v]" -map "[aout]" -t 12 -c:v libx264 -crf 16 -preset slow -c:a aac -b:a 320k final_12s.mp4
```
(No Resolve/Premiere: crossfade de áudio de ~5 frames na junção dá o mesmo resultado. Se o estalo do chute vier depois de 0,3 s, apare o início do clipe 1 e compense no clipe 2.)

**Se um take sair ruim — o que mudar**

| Sintoma | Ajuste |
|---|---|
| Planos fundidos ou fora de ordem | Regerar (nova seed / novas 4 saídas); confirmar "Hard cut to:" no início dos planos 2 e 3; tirar carga: plano 1 sem push-in (câmera estática). Último recurso: clipe 1 de 6 s (mãos + impedimento) + clipe 2 de 6 s ([00:00-00:02] carrinho+cartão, [00:02-00:04] pênalti, [00:04-00:06] linha do gol) emendados |
| Placar, letras, números, escudo, telão | Descartar (não dá para apagar em pós). `enhancePrompt: false` se possível; reforçar "plain blank kits", "no screens or banners", "nothing drawn over the picture" |
| Cartão laranja/vermelho/branco | Descartar; acrescentar ao plano 3 "the card is the only yellow object in this shot" |
| Goleiro fora da área ou sem gol atrás | Descartar; reforçar "well inside his area, the goal and net directly behind him, the penalty-area line between camera and goalkeeper" |
| Impedimento ilegível (atacante atrás da linha, bola no chão, passador ausente) | Trocar "two full steps" por "three full steps"; "the shot opens on the blue passer's boot leaving the ball, the ball in the air at head height"; opcional: linha fina na altura do defensor em pós (câmera estática facilita) |
| Bola atravessa as luvas / bola dupla | Descartar; manter "one single ball"; "the ball stops dead in his gloves" |
| Sotaque europeu, voz feminina, voz com som de rádio, fala cortada | Regerar; manter "Brazilian football commentator voice, clean full-range studio recording"; se a 1ª frase estourar, "Mão? Só o goleiro." (5 sílabas); último recurso: locução humana/TTS em pós mantendo SFX e torcida |
| Personagem mexe os lábios com a narração | Regerar; "Voice-over narration only; nobody on screen speaks" está no cabeçalho e "lip-sync, talking faces" no negative |
| Extend fica no árbitro e não faz o whip pan | Regerar; na 2ª falha, trocar a abertura do Prompt B por "Hard cut to a new shot: wide low static view from behind and slightly beside the blue striker..." (corte seco); na 3ª, migrar para a Rota B |
| Whip pan borrado demais / longo demais | Cortar dentro do borrão (zona segura); se o whip ocupar > 0,8 s, apagar frames do meio do borrão |
| Dois apitos | Regerar; manter "one short referee whistle" como único apito no SFX; se persistir, silenciar o 2º em pós |
| Bola cruza longe da lente / goleiro cai por cima da linha em primeiro plano | Descartar; reforçar "just inside the left post", "one meter from the lens", "the goalkeeper dives toward the far post" |
| "Goooool!" antes de a bola cruzar | Regerar a parte 2; ou cortar frames congelados da junção para realinhar; ou regravar a VO em pós |
| Grito curto demais (< 1,2 s) | Apagar frames congelados da junção (traz o gol para ≤ 10,8 s); nunca pôr fade; em último caso VO em pós |
| Rota B parece começar parada | Aparar o início do clipe 2 com `-ss`; reforçar "already two strides into his run-up" como primeiras palavras da ação |
| Salto de nitidez/cor na junção | Nunca misturar 720p e 1080p; regerar a parte 2 na resolução do clipe 1; match de cor leve em pós |
| Chute inteiro em câmera lenta | Aceitável; se quiser impacto, acrescentar "no slow motion in this shot" ao plano do pênalti |
| Rosto parecido com jogador famoso | Descartar; alterar um traço (barba, cabelo) no CAST e regerar |

**QA do master (antes de entregar)**
- Duração 12,00 s exatos; estalo do chute até 0,3 s.
- Bola inteira dentro da linha até 10,8 s; "Goooool!" ≥ 1,2 s, sem fade, corte seco no rugido.
- Nenhum texto, número, escudo, telão ou placa gerados; nenhum rosto de atleta real; uma só bola.
- Sem salto de nitidez, cor ou luz na junção dos 8 s; mesma voz nas duas metades (ou VO única em pós).
- Um só apito na parte 2; ninguém mexe os lábios com a narração.
- -14 LUFS / TP -1.
- Rótulos dentro da safe area no 9:16; versão limpa (sem texto) arquivada.
- Exportação 4K (upscale do master 720p) e cópia 1080p para redes.

---

## 10. Por que este prompt funciona — decisões intocáveis

- **2 s + 3 s + 3 s em 8 s, uma câmera e um sujeito por plano, um único hold (fim do plano 3)**: dentro da faixa segura do timestamp prompting, com verbos físicos ("thumps", "snaps", "slides in", "bulges") e "Hard cut to:" abrindo cada plano novo.
- **Geometria que prova a regra**: linha da área entre câmera e goleiro + gol atrás dele (mãos); pé do passador em quadro + bola no ar + dois passos + goleiro ao fundo + foco profundo (impedimento); carrinho atrasado pelo lado (imprudente, não violento); árbitro apontando a marca (pênalti); câmera deitada na linha junto ao poste e grama visível entre bola e linha (gol).
- **Código de cores**: laranja (goleiro), bandeira quadriculada e amarelo (cartão) como únicas cores quentes; azul royal de cima a baixo x branco com calção preto — sem "kit bleed".
- **Narração enxuta e medida em sílabas**: 18 palavras / ≤ 5 síl/s, uma linha por plano, VO-only, voz de estúdio limpa; "rádio" só no "Goooool!".
- **Arco sonoro**: estalo no frame 0, apito único, hush de um tempo, chicote da rede, explosão com batucada e grito arrastado em corte seco no auge; sem música no clipe 1 (a batucada é a cama).
- **Engenharia de continuidade**: hold do cartão como ponto de corte; whip pan a favor do contexto do Extend; Rota B sem first frame (corte seco não precisa dele); 720p nas duas metades; seed só reaproveitada na parte 2; frames congelados da junção como "válvula" de tempo.
- **Limites honestos**: o Extend *tende a* manter voz e cama (gerar 2–4 e escolher; VO em pós como reserva); os planos 2–4 leem no mudo, o plano 1 depende da narração ou do rótulo em pós.
- **Simplificações assumidas e declaradas**: "mão" = toque deliberado / braço em posição antinatural (o arremesso lateral e o toque acidental ficam fora do vídeo); "último defensor" = penúltimo adversário da Regra 11 (o goleiro, ao fundo na linha do gol, é o último, por isso a imagem o mostra atrás de todos); a bandeira sobe no instante do passe (na regra, a assistente espera a participação ativa — *wait and see*); "falta imprudente" = amarelo (força excessiva = vermelho); os quatro lances são momentos distintos da mesma partida, não uma jogada contínua (o impedimento interrompe o jogo).

---

## 11. Alternativa de estilo (plano B)

Segundo colocado no ranking de estilos: **animação 3D estilizada, dia claro, cores chapadas** — máxima legibilidade didática, zero risco de rostos reais, escudos e telões, e geometria mais fácil para o modelo. Perde a "assinatura cinematográfica" do plano A, mas é o teste certo se o cliente achar o noturno escuro demais ou quiser um tom mais leve/educativo. Mesma estrutura (3 planos, 2+3+3), mesma narração, mesmas rotas.

**Prompt A-alt — clipe 1 (8 s), compacto (~300 palavras):**

```text
Stylized 3D animated football explainer, clean modern CG render, bright daylight, soft global illumination, saturated flat colors, simple rounded characters with clear silhouettes, smooth motion. A small sunny stadium with plain green stands and no screens or banners, crisp white lines on vivid green grass, nothing drawn over the picture. Three shots joined by hard cuts. Voice-over narration only; nobody on screen speaks.

CAST, plain blank kits, no crests, sponsors or numbers. GOALKEEPER: bright orange jersey, black gloves. BLUE STRIKER: royal-blue shirt, shorts and socks, dark skin, short curly hair. WHITE TEAM: white shirts, black shorts and socks. REFEREE: all black. One single white ball with black panels.

[00:00-00:02] Low wide static camera just outside the penalty area, looking into the box toward the goal. The orange goalkeeper, inside his area with the goal behind him, catches the ball in both gloves and hugs it to his chest; the penalty-area line crosses the foreground between camera and goalkeeper. SFX: a soft thump. The commentator says in Brazilian Portuguese, "Mão? Só o goleiro, na área."

[00:02-00:05] Hard cut to: elevated static camera on the touchline, level with the last white defender, slow motion. A blue teammate at the left edge has just kicked the ball; the ball flies slowly toward the blue striker, who stands two full steps closer to the goal (frame right) than the last white defender; the orange goalkeeper small on his goal line at the far right; an assistant referee in black at the left snaps a checkered flag straight up. SFX: a soft whoosh, a flag snap. The commentator says in Brazilian Portuguese, "Além do último defensor? Impedimento."

[00:05-00:08] Hard cut to: low static side camera inside the penalty area, real-time speed. A white defender slides in late from the side and catches the striker's ankle; the striker falls and stays down; the referee steps into the foreground, blows the whistle once and raises a big bright yellow card, then holds perfectly still with the card raised for the last second. SFX: a slide, one whistle. The commentator says in Brazilian Portuguese, "Falta imprudente? Amarelo."

AUDIO: deep, warm male Brazilian football commentator voice, clean studio recording, unhurried, one short line per shot with silence between lines, louder than the ambience. Ambient noise: light crowd murmur. Music: a playful, bouncy marimba and light percussion groove, quiet under the voice.
```

**Parte 2 (8–12 s) no plano B:** use os Prompts B (Extend) ou C (Rota B) da seção 3 trocando apenas o primeiro parágrafo pelo cabeçalho de estilo acima ("Stylized 3D animated football explainer ... nothing drawn over the picture.") e acrescentando ao AUDIO: `Music: the marimba groove stops at the whistle; after the net bulges, only the crowd and the commentator.` Negative prompt: a lista da seção 4 **sem** "cartoon, anime" e **com** "photorealistic, live action, film grain". Rótulos em pós e QA idênticos aos da seção 5 e 9.
