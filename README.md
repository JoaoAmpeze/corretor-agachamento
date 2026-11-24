# Corretor de Agachamento

Aplicativo de visão computacional que acompanha o **agachamento livre** pela webcam ou por um vídeo gravado.

- **Durante o treino:** conta as repetições, dá uma **nota de 0 a 100** para cada uma, calcula o **percentual de acerto** e **fala** as correções na hora.
- **Antes do treino:** um guia mostra o movimento correto.
- **Depois do treino:** um resumo e o histórico mostram a evolução.

Trabalho do componente **Robótica e Visão Computacional**, curso de Ciência da Computação da Unochapecó (prof. Wagner Titon).

**Integrantes:** João Ampeze, João Chiarello, Bruno da Costa e José Tourinho

**Vídeo de apresentação:** https://youtu.be/E8kPcGYKOZM

### Como rodar (resumo)

1. Instale o **Python 3.10 ou mais recente**.
2. **Windows:** dê dois cliques em `iniciar.bat`. **Linux/macOS:** rode `./iniciar.sh`.
3. O navegador abre em http://localhost:5000. Na primeira vez, o script instala as dependências e baixa o modelo de pose (precisa de internet).

Para rodar os testes: `python -m pytest`. Detalhes em [Instalação](#instalação), [Execução](#execução) e [Testes](#testes).

### Onde está cada parte do código

| Parte | Arquivo |
|---|---|
| Detecção dos 33 pontos do corpo (MediaPipe) | `src/detector_pose.py` |
| Ângulos e distâncias | `src/geometria.py` |
| Regras: fases do movimento, contagem, 15 critérios e nota | `src/analisador_agachamento.py` |
| Treino guiado: séries, descanso, voz e fadiga | `src/treino.py` |
| Servidor web e laço de captura/análise | `app.py` |
| Interface (telas do app) | `web/` |
| Testes automatizados | `tests/` |

---

## O problema

Uma pesquisa feita pelo grupo com 15 pessoas (13 praticantes de musculação) mostrou que:

- **85%** dos praticantes já sentiram dor ou tiveram lesão que associam a um exercício executado de forma errada; **64%** destes precisaram se afastar dos treinos;
- **62%** têm dúvida sobre a execução com frequência e **62%** têm dificuldade de encontrar um instrutor disponível;
- **46%** treinam sozinhos, seguindo a ficha ou vídeos da internet;
- o **agachamento livre** foi o exercício com mais dúvidas, e **joelho** e **lombar** foram as regiões com mais dor.

Nas academias, há poucos instrutores para muitos alunos, e o aluno não consegue ver a própria postura enquanto treina. Com isso, os erros se repetem sem correção.

## A solução

O app é um "personal virtual" para o agachamento, inspirado em aplicativos de treino com câmera. O visual segue a linguagem da Apple: fundo claro, cartões brancos, anéis de progresso no estilo do app Atividade, efeito de vidro e uma "ilha" sobre o vídeo com o status do treino. Há também modo escuro, no botão da lua.

| Tela | O que faz |
|---|---|
| **Início** | Painel com total de treinos, repetições, acerto geral, nota média, gráfico de evolução e treinos recentes |
| **Treinar** | Monta o treino: séries, repetições, descanso (ou modelos prontos: Clássico 3×10, Força 4×8, Resistência 2×15, Livre); escolhe webcam ou vídeo e a posição da câmera |
| **Treino ao vivo** | Dois modos, que podem ser trocados a qualquer momento: **normal**, com o vídeo, um painel com o anel de repetições, a nota de cada articulação na última repetição e um cartão com a mensagem do treinador; e **tela cheia**, feita para ver de longe, com o vídeo ocupando a tela, números grandes nos cantos e a mensagem numa barra fixa embaixo (nada cobre a pessoa). Nos dois: esqueleto com as articulações avaliadas destacadas, contagem regressiva, descanso cronometrado e **voz** |
| **Resumo** | Anéis de acerto, nota média e meta, melhor nota, gráfico de nota por repetição, erros mais frequentes, tabela com as medidas de cada repetição e uma dica para o próximo treino |
| **Como fazer** | Animação do agachamento correto com o ângulo do joelho, passo a passo e explicação dos critérios e da nota |
| **Histórico** | Todos os treinos salvos, com gráfico de evolução do % de acerto e da nota |

### O que é avaliado

O app usa 12 pontos do corpo detectados pelo modelo: ombros, quadris, joelhos, tornozelos, calcanhares e pontas dos pés, mais as orelhas para a cabeça. Com eles, avalia **15 critérios**, escolhidos pelos erros que mais causam lesão no agachamento:

| Critério | Articulações usadas | Como é medido | Correto | Vista |
|---|---|---|---|---|
| **Profundidade** | quadril, joelho, tornozelo | Menor ângulo do joelho na repetição (3D) | até 100° | todas |
| **Tronco** | ombro, quadril | Maior inclinação do tronco em relação à vertical | até 50° | lateral |
| **Tronco × canela** | ombro, quadril, joelho, tornozelo | No fundo, inclinação do tronco menos a da canela (o ideal é ficarem quase paralelos) | até 25° a mais | lateral |
| **Quadril antes do peito** | ombro, quadril | Na subida, quanto o tronco deita além da posição do fundo (o quadril sobe sozinho e sobrecarrega a lombar) | até 12° | lateral |
| **Peso no meio do pé** | ombro, quadril, calcanhar, ponta do pé | Distância horizontal entre o meio do tronco e o meio do pé, em comprimentos de pé | até 0,6 | lateral |
| **Calcanhar** | tornozelo, calcanhar, ponta do pé | Quanto o calcanhar sobe em relação à ponta do pé, comparado com a posição em pé | até 8% da canela | lateral |
| **Cabeça** | orelha, ombro, quadril | Ângulo entre o pescoço e a linha do tronco | até 50° | lateral |
| **Joelhos para dentro** (valgo) | joelhos, tornozelos | Distância entre os joelhos ÷ distância entre os tornozelos, na parte baixa | pelo menos 0,75 | frontal |
| **Joelho × ponta do pé** | quadril, joelho, ponta do pé | Desvio de cada joelho em relação à linha quadril → ponta do pé (pega quando só uma perna entra ou sai) | até 20% da base | frontal |
| **Simetria** | quadris, joelhos, tornozelos | Inclinação da linha dos quadris, quadril fora do centro dos pés e diferença entre os dois joelhos | até 7°, 15% e 15° | frontal |
| **Ombros nivelados** | ombros | Inclinação da linha dos ombros | até 8° | frontal |
| **Base dos pés** | ombros, tornozelos | Distância entre os pés ÷ largura dos ombros, no início da repetição | entre 0,8 e 2 | frontal |
| **Extensão no topo** | quadril, joelho, tornozelo | Quanto faltou para a pessoa ficar em pé (comparado com o maior "em pé" dela no treino) antes de começar a repetição | até 15° | todas |
| **Controle no fundo** (quique) | quadril, joelho, tornozelo | Velocidade do joelho ao chegar e ao sair do ponto mais baixo (as duas altas = quique) | até 130°/s | todas |
| **Ritmo** | – | Tempo da descida | 0,6 s ou mais | todas (só na nota) |

Além disso, o treino guiado avalia a **fadiga na série**: se a nota média das duas últimas repetições cai 20 pontos ou mais em relação às duas primeiras, ou se a profundidade piora 12° ou mais, o app avisa (na tela e por voz) que a técnica está caindo e sugere encerrar a série. O resumo mostra em quais séries isso aconteceu.

Uma repetição é **correta** quando não tem nenhum erro de técnica. O **% de acerto** é o número de repetições corretas dividido pelo total. O ângulo do quadril (ombro–quadril–joelho) também é medido e aparece no relatório. No resumo, clicar numa repetição mostra a nota e o valor medido de cada critério.

**O que a câmera não consegue avaliar** (limitação do modelo, que não tem pontos na coluna nem no arco do pé): arredondamento da lombar no fundo, arco do pé desabando, respiração e carga da barra. "Joelho passando da ponta do pé" não é tratado como erro, porque é um movimento natural do agachamento e reduz a carga na lombar.

**Nota de cada repetição:**

- Cada critério vira uma nota de 0 a 100, por interpolação linear. No limite do erro, a nota do critério é 70. Por exemplo, na profundidade: 90° vale 100, 100° vale 70 e 140° vale 0.
- A nota final combina o **pior critério de técnica (60%)** com a **média de todos os critérios (40%)**. Assim, um erro grave não fica escondido pelos outros critérios.
- Faixas: 85–100 Excelente · 70–84 Boa · 50–69 Regular · 0–49 Precisa melhorar.

### Funcionamento (entrada → processamento → saída)

```
Webcam ou vídeo (OpenCV)
  → MediaPipe Pose Landmarker (BlazePose): 33 pontos do corpo em 2D (pixels) e 3D (metros)
  → ângulos e distâncias + suavização (média móvel exponencial)
  → máquina de estados do movimento: em pé → descendo → subindo → em pé (= 1 repetição)
  → avaliação da repetição (erros + nota)
  → treino guiado: contagem regressiva → série → descanso → ... → fim
  → navegador: vídeo com esqueleto (MJPEG) + estado em JSON + voz natural (edge-tts) ou do navegador
  → histórico (JSON) e relatório (CSV)
```

- **Ângulo do joelho:** usa as coordenadas **3D** do MediaPipe, então não depende do ângulo da câmera.
- **Tronco e joelhos:** usam as coordenadas **2D** da imagem, cada um na vista em que a medida é confiável.
- **Posição da câmera:** é detectada pelo giro do corpo em 3D, ou seja, o ângulo da linha dos quadris e dos ombros em relação à câmera. Abaixo de 25° é **de frente**, acima de 65° é **de lado** e no meio é **diagonal**. Na diagonal, as medidas feitas na imagem (pés, joelhos × pé, ombros, simetria) ficam distorcidas pela perspectiva. Por isso o app avalia só os critérios medidos em 3D (profundidade, tronco, quadril antes do peito, extensão, controle e ritmo) e avisa que, para a análise completa, é melhor filmar de lado ou de frente.
- **Contagem de repetições (adaptativa):**
  - Na prática, a perna "esticada" não mede 180°: costuma ficar entre 150° e 170°, conforme a pessoa, a câmera e o modelo. Por isso o app usa como referência "em pé" o maior ângulo do joelho visto recentemente.
  - A repetição começa quando o joelho dobra **15°** abaixo dessa referência e termina quando a pessoa já voltou boa parte do caminho (a 12° da referência ou a 40% da amplitude, o que for maior). Assim também conta quem não estica totalmente; isso é avaliado à parte, no critério "Extensão no topo".
  - Movimentos com menos de **30°** de amplitude não contam. Isso evita repetições falsas por tremedeira ou ajuste de postura.
  - Cada repetição é contada na hora em que a pessoa sobe, com destaque no vídeo e por voz.
  - Durante a contagem regressiva e o descanso, nada é contado.
- **Lado analisado:** na vista lateral, o app usa a perna virada para a câmera. Ele só troca de lado com uma diferença clara de visibilidade, para o ângulo não pular entre as duas pernas.
- **Vídeo gravado:** a pessoa do vídeo não para para descansar, então as séries seguem direto, sem contagem regressiva e sem descanso. O treino termina quando o vídeo acaba. A contagem regressiva e o descanso usam o relógio real.

**Arquitetura:**

- O Python (Flask) roda a captura e a análise numa *thread* separada.
- A webcam é lida em outra *thread* (`src/captura.py`), que guarda só o quadro mais recente. Se a análise de um quadro demora mais que o intervalo da câmera, os quadros que chegaram no meio são descartados, em vez de ficarem acumulados num buffer. Assim o vídeo não vai ficando atrasado em relação ao movimento.
- Ele envia para o navegador o vídeo com o esqueleto desenhado (`/video`, só quando há quadro novo) e o estado do treino em JSON (`/api/estado`, consultado a cada 120 ms).
- A página web mostra os dados e fala a contagem e as correções.
- A voz natural (Francisca ou Antônio) é gerada no Python com vozes neurais em português e guardada em `dados/voz/`, então cada frase só é gerada uma vez. Sem internet, o app usa a voz do navegador.

## Tecnologias

- **Python 3.10 ou mais recente** (testado com 3.12 e 3.13)
- **MediaPipe** (Pose Landmarker, modelo **BlazePose**): rede neural pré-treinada do Google para estimativa de pose
- **OpenCV**: captura da câmera e do vídeo, desenho do esqueleto e codificação JPEG
- **NumPy**: cálculo de ângulos e distâncias
- **Flask**: servidor web local com a API do app
- **HTML, CSS e JavaScript** puros, sem bibliotecas externas; gráficos desenhados em SVG
- **edge-tts**: voz natural em português (vozes neurais Francisca e Antônio), com a **Web Speech API** do navegador como alternativa sem internet
- **Pillow**: textos com acento no modo simples
- **pytest**: testes automatizados

## Estrutura

```
app.py                          # aplicativo web (servidor Flask + thread de captura e análise)
main.py                         # modo simples: janela do OpenCV, sem navegador
iniciar.bat / iniciar.sh        # instalam as dependências na primeira vez e abrem o app
requirements.txt                # dependências do Python
src/
  captura.py                    # leitura da webcam numa thread (sempre o quadro mais recente)
  detector_pose.py              # MediaPipe: detecção dos 33 pontos e download do modelo
  geometria.py                  # ângulos, distâncias e suavização
  analisador_agachamento.py     # regras: fases, repetições, erros e nota
  treino.py                     # treino guiado: séries, descanso, contagem regressiva e mensagens de voz
  historico.py                  # histórico de treinos (dados/historico.json)
  voz.py                        # voz natural do treinador (gera e guarda os áudios das frases)
  interface.py                  # desenho do esqueleto (e do painel no modo simples)
  relatorio.py                  # relatório CSV
web/
  index.html, style.css, app.js # interface do app
tests/                          # testes automatizados com poses simuladas
```

Pastas criadas pelo app ao rodar (não vão para o repositório): `models/` (modelo de pose baixado na primeira execução), `dados/` (histórico e áudios da voz), `resultados/` (relatórios CSV) e `uploads/` (vídeos enviados).

## Instalação

```bash
git clone https://github.com/JoaoAmpeze/corretor-agachamento.git
cd corretor-agachamento
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

Na primeira execução, o programa baixa automaticamente o modelo `pose_landmarker_full.task` para a pasta `models/`. Se o download falhar, baixe pelo link exibido no terminal e salve na pasta `models/`.

## Execução

**Jeito mais fácil:**

- **Windows:** dê dois cliques em `iniciar.bat`.
- **Linux ou macOS:** rode `./iniciar.sh`.

O script cria o ambiente virtual, instala as dependências na primeira vez e abre o app. A única coisa que precisa estar instalada antes é o Python.

**Manual** (depois da instalação acima):

```bash
python app.py
```

O navegador abre em **http://localhost:5000**. Para encerrar, aperte `Ctrl+C` no terminal.

| Opção | Para que serve |
|---|---|
| `--porta 8000` | usa outra porta |
| `--modelo lite` | modo de desempenho padrão: `lite` = Rápido, `full` = Equilibrado, `heavy` = Preciso (também dá para trocar na tela **Treinar**) |
| `--sem-navegador` | não abre o navegador automaticamente |

**Modo simples** (janela do OpenCV, sem navegador):

```bash
python main.py                                  # webcam
python main.py --fonte video.mp4 --salvar-video resultados/analise.mp4
```

Teclas do modo simples: `Q` sai, `R` zera, `S` salva um print, `ESPAÇO` pausa.

**Desempenho (se a câmera ficar lenta ou atrasada):**

Em **Treinar → Câmera → Desempenho** há três modos:

| Modo | Modelo | Imagem | Quando usar |
|---|---|---|---|
| Rápido | BlazePose *lite* | 960×540 | notebooks mais simples, sem placa de vídeo |
| Equilibrado | BlazePose *full* | 1280×720 | padrão |
| Preciso | BlazePose *heavy* | 1280×720 | computador mais forte; detecta melhor quando a pessoa está longe |

- O número de **quadros analisados por segundo (fps)** aparece em cima do vídeo e fica amarelo abaixo de 12 fps. Abaixo disso a análise perde parte do movimento, e vale trocar para o modo Rápido.
- O app pede à webcam o formato **MJPG**. Muitas webcams USB entregam 720p a só 5–10 fps no formato padrão (YUY2) e a 30 fps em MJPG.
- Outras dicas: feche outros programas que usam a câmera ou a CPU (videochamadas, muitas abas abertas); deixe o notebook **ligado na tomada** (na bateria o processador fica mais lento); e use boa iluminação. Com pouca luz a webcam aumenta o tempo de exposição e entrega menos quadros por segundo.

**Dicas para um bom resultado:**

- corpo inteiro (da cabeça aos pés) na imagem;
- câmera a cerca de 2 a 3 metros, na altura do quadril;
- **de lado** para avaliar profundidade e tronco, **de frente** para avaliar os joelhos;
- ambiente iluminado e roupa que contraste com o fundo;
- a voz é escolhida em **Treinar → Treinador por voz** (botão "Ouvir" para testar) e pode ser desligada no ícone de som do menu.

## Testes

```bash
python -m pytest
```

São 43 testes com poses simuladas (geradas com ângulos conhecidos) e uma câmera falsa, sem precisar de webcam. Eles verificam:

- a contagem de repetições;
- cada um dos erros;
- a nota de cada repetição;
- que a tremedeira não gera repetições falsas;
- o treino guiado: contagem regressiva, séries, descanso (repetições feitas no descanso não contam), pular descanso e conclusão;
- a contagem adaptativa (perna que não estica toda, movimentos pequenos que não contam, lado estável);
- os critérios detalhados: calcanhar, tronco × canela, simetria, base dos pés, quadril antes do peito, peso no meio do pé, cabeça, extensão no topo, quique no fundo, joelho × ponta do pé e ombros;
- o aviso de fadiga na série;
- a detecção da posição da câmera (de lado, de frente e diagonal);
- os eventos de voz e o relatório;
- a leitura da webcam em *thread*: com a análise mais lenta que a câmera, ela recebe sempre o quadro mais novo, sem atraso acumulado.

### Testes com vídeo

**Calibração com vídeos reais de execução correta.** Usamos três vídeos de demonstração de agachamento bem executado, que deveriam receber notas altas:

| Vídeo | Câmera | Antes do ajuste | Problema encontrado | Depois do ajuste |
|---|---|---|---|---|
| Agachamento livre sem peso (4 repetições) | diagonal (~45°) | nota ~30, 0 de 4 corretas | a câmera na diagonal era tratada como "de frente", e a perspectiva gerava falsos erros de simetria, joelho × pé e ombros | notas 93–100, 4 de 4 corretas |
| Agachamento com halteres (3 repetições) | de frente | nota ~65, 0 de 3 corretas | joelhos abertos acompanhando os pés (correto) eram contados como "fora da linha do pé" | notas 99–100, 3 de 3 corretas |
| Agachamento livre, de frente → de lado → de frente (13 repetições) | muda no meio do vídeo | parte de frente com notas 46–79 e 1 de 5 corretas | (1) a diferença entre os joelhos medida em 3D oscila muito de frente (picos de 15–18° num agachamento simétrico); (2) o joelho em pé mede ~174° de lado e ~158° de frente, então a referência "em pé" da parte lateral gerava "não estendeu" na parte frontal; (3) quadros isolados com pontos fora do lugar viravam erro | notas 88–100, 13 de 13 corretas, contagem 13 de 13 |

Correções feitas:

- detecção de câmera em 3D, com a nova vista **diagonal**;
- o critério joelho × ponta do pé passou a acusar só o joelho indo **para dentro** (valgo);
- a simetria, de frente, passou a usar também a inclinação da linha dos quadris, medida na imagem e mais estável;
- a referência de "em pé" é separada por posição de câmera e recomeça quando a posição muda;
- cada critério usa o **percentil 80** dos valores da repetição, e não o máximo, para que um quadro isolado com erro do modelo não vire erro da repetição;
- os alertas na tela só aparecem se o problema continuar por 4 quadros seguidos;
- quando a posição da câmera muda no meio de uma repetição, ela é marcada como "mista" e só os critérios 3D valem.

Os testes foram feitos com o mesmo modelo de pose (BlazePose) rodando quadro a quadro nos vídeos.

### Testes do grupo com a webcam

O grupo também testou o app ao vivo, com a webcam, gravando de lado, de frente e na diagonal: agachamentos corretos e com erros feitos de propósito (raso, tronco muito inclinado, joelhos para dentro), além da pessoa saindo da imagem, para conferir a contagem, os erros acusados e os avisos.

- O app reconheceu **cerca de 80%** dos agachamentos e erros feitos nos testes.
- A câmera precisa ficar mais longe, com o corpo inteiro na imagem: perto demais, o modelo detecta menos pontos e o app erra mais.
- Nos primeiros testes o app errava bastante, porque detectava menos pontos do corpo; os ajustes feitos depois disso melhoraram a detecção.

## Limitações e melhorias

**Limitações:**

- analisa só o agachamento e uma pessoa por vez;
- os limites (100°, 50°, 0,75) são valores gerais e não consideram diferenças de corpo, mobilidade ou variação do exercício;
- a precisão cai com corpo parcialmente fora da imagem, pouca luz, roupas largas ou barra e anilhas cobrindo o corpo;
- não verifica lombar arredondada nem o arco do pé (o modelo não tem pontos na coluna nem no arco do pé);
- não substitui a orientação de um profissional de educação física.

**Melhorias possíveis:**

- incluir outros exercícios, como levantamento terra, rosca direta e supino;
- calibrar os limites com profissionais e com vídeos rotulados;
- criar perfis de usuário;
- criar uma versão para celular.

## Referências

- BAZAREVSKY, V. et al. *BlazePose: On-device Real-time Body Pose tracking*. arXiv:2006.10204, 2020.
- LUGARESI, C. et al. *MediaPipe: A Framework for Building Perception Pipelines*. arXiv:1906.08172, 2019.
- Documentação do MediaPipe Pose Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
