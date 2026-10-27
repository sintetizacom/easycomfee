# `krea2-anygles-nativo` — o nó de cola do "Outro ângulo da pessoa"

Estes três arquivos são **código nosso**, mas rodam dentro do ComfyUI, em
`custom_nodes/krea2-anygles-nativo/`. A cópia aqui existe porque aquela pasta
**não está sob versão** — se a instalação do ComfyUI for refeita, o trabalho de
um dia inteiro se perde sem deixar rastro.

**A cópia que roda é a de lá.** Esta é o original versionado. Ao mexer numa,
copie para a outra — não há sincronia automática, de propósito: um script que
copia sozinho acabaria sobrescrevendo a versão boa na hora errada.

## Para instalar numa máquina nova

```bash
# 1. o pacote do autor, SEM o requirements.txt dele
cd ComfyUI/custom_nodes
git clone https://github.com/alexw5702-afk/krea2-anygles

# 2. os dois pacotes que faltam, POR NOME
#    nunca `pip install -r`: o requirements.txt dele lista `torch` sem versao
#    e reinstalaria o torch da maquina
ComfyUI/.venv/Scripts/python.exe -m pip install pyrender "pyglet<2"

# 3. o pyrender crava PyOpenGL==3.1.0, de 2015, que quebra em Python moderno
#    ("startswith first arg must be bytes"). Restaurar:
ComfyUI/.venv/Scripts/python.exe -m pip install "PyOpenGL==3.1.10"

# 4. este pacote, ao lado do dele
cp -r no-anygles ComfyUI/custom_nodes/krea2-anygles-nativo
```

Faltam ainda, e **não são código**:

- o LoRA `krea2_anygles_rank32.safetensors` (0,21 GB) em `models/loras/Krea/`
- o checkpoint `sam_3d_body_dinov3_bf16.safetensors` em `models/detection/SAM3/`
- a linha `detection: detection` no `extra_model_paths.yaml`, na seção
  `quentes` — **sem ela o seletor do SAM3D vem vazio** e a geração é recusada
  na validação, com uma mensagem que não explica nada

O resto do porquê está no `NOTAS-MOTOR.md`, inclusive por que o render roda num
subprocesso e por que o shader `normals` nativo **não** serve.
