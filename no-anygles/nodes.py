# coding: utf-8
"""Anygles usando o SAM 3D Body NATIVO do ComfyUI.

POR QUE ESTE NO EXISTE. O `Krea2AnyglesCamera` publicado faz duas coisas: (1)
recupera a malha humana com a inferencia propria do SAM 3D Body e (2) renderiza
o mapa que o LoRA consome. A parte (1) exige o repositorio GATED da Meta
completo — inclusive `assets/mhr_model.pt` — cuja liberacao e manual e pode
demorar dias, mais MoGe, hydra, pytorch-lightning e companhia.

O ComfyUI ja traz SAM 3D Body nativo, e o checkpoint ja esta no disco. Entao
aqui a parte (1) vem do `SAM3DBody_Predict` nativo e a parte (2) continua sendo
o CODIGO DELES, chamado sem alteracao.

POR QUE NAO USEI O SHADER `normals` NATIVO, que pareceria o obvio: o que eles
chamam de "target normal" NAO e um mapa de normais. Olhando o `_render`:

    fused[..., :2] = color[..., :2]        # R,G = normal X,Y
    fused[..., 2]  = rint(near * 255)      # B = PROFUNDIDADE invertida

O canal azul carrega profundidade normalizada por percentil (2 a 98), nao o Z
da normal. O shader nativo poe `+Z -> B`, pelo proprio tooltip dele. Trocar um
pelo outro daria um mapa plausivel e ERRADO, com o LoRA recebendo no azul algo
que nunca viu no treino — defeito que nao aparece olhando o mapa, so no
resultado final, e mesmo assim como "qualidade ruim" em vez de "canal trocado".

Por isso a renderizacao e importada do arquivo deles, e nao reescrita.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

_ORIGEM = Path(__file__).resolve().parent.parent / "krea2-anygles"


def _renderiza_fora(vertices, faces, camera, focal, largura, altura, escala,
                    deslocamento):
    """Chama o render do autor NUM PROCESSO A PARTE.

    Solto, o pyrender roda nesta maquina — testado, inclusive dentro de uma
    thread. Dentro do ComfyUI, o mesmo codigo morre em `renderer.delete()` com
    "Attempt to retrieve context when no valid context". A explicacao obvia
    (no executado em thread de trabalho, contexto OpenGL preso a thread) foi
    TESTADA E NAO SE SUSTENTA: em processo novo, dentro de thread, funciona.

    Sobra interacao com o que ja esta carregado no servidor. Isolar custa ~1 a
    3 s e resolve a classe toda; caçar qual dos vinte e tantos nos customizados
    e o culpado resolveria uma instancia, e um contexto OpenGL vazando num
    processo que fica dias no ar e pior que o custo do processo.

    O `PYOPENGL_PLATFORM` sai do ambiente do filho porque o pyrender so escolhe
    o caminho de desktop quando a variavel esta AUSENTE — e o modulo do autor
    define "egl" sozinho ao carregar.
    """
    pasta = Path(tempfile.mkdtemp(prefix="anygles_"))
    try:
        entrada, saida = pasta / "malha.npz", pasta / "normal.png"
        np.savez(entrada, vertices=vertices, faces=faces, camera=camera,
                 focal=np.float32(focal), largura=np.int32(largura),
                 altura=np.int32(altura), escala=np.float32(escala),
                 deslocamento=np.asarray(deslocamento, dtype=np.float32))
        ambiente = dict(os.environ)
        ambiente.pop("PYOPENGL_PLATFORM", None)
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "render_normal.py"),
             str(entrada), str(saida), str(_ORIGEM)],
            capture_output=True, text=True, timeout=300, env=ambiente)
        if r.returncode != 0 or not saida.is_file():
            # A saida do filho vem junto: sem ela, um erro de OpenGL aqui
            # aparece como "o no falhou" e nao se sabe por que.
            raise RuntimeError(
                "o render do mapa falhou (codigo %s)\n%s"
                % (r.returncode, (r.stderr or r.stdout or "")[-1500:]))
        return Image.open(saida).convert("RGB").copy()
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def _importa(nome: str):
    """Carrega um arquivo do pacote deles PELO CAMINHO.

    A pasta se chama `krea2-anygles`, com hifen, que nao e nome valido de
    modulo em Python — `import krea2_anygles` nao acha nada. Os dois arquivos
    usados aqui so importam stdlib, numpy e PIL no topo (o pyrender e
    importado dentro da funcao), entao carregam soltos sem efeito colateral.
    """
    caminho = _ORIGEM / (nome + ".py")
    if not caminho.is_file():
        raise FileNotFoundError(
            "nao achei %s — o pacote krea2-anygles precisa estar clonado ao "
            "lado deste, em custom_nodes/" % caminho
        )
    spec = importlib.util.spec_from_file_location("_anygles_" + nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_normal = _importa("sam3d_normal")
_anygles = _importa("anygles")


def _para_pil(imagem: torch.Tensor) -> Image.Image:
    if imagem.ndim != 4 or imagem.shape[0] != 1 or imagem.shape[-1] < 3:
        raise ValueError("esperava uma IMAGE [1,H,W,C], veio %s"
                         % (tuple(imagem.shape),))
    a = (imagem[0, ..., :3].detach().float().clamp(0, 1).mul(255).round()
         .to(torch.uint8).cpu().numpy())
    return Image.fromarray(a, mode="RGB")


def _para_tensor(imagem: Image.Image) -> torch.Tensor:
    a = np.asarray(imagem.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(a).unsqueeze(0)


class Krea2AnyglesCameraNativo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": ("IMAGE",),
                "mhr_pose_data": ("MHR_POSE_DATA",),
                "yaw": ("FLOAT", {"default": 50.0, "min": -180.0, "max": 180.0,
                                  "step": 10.0}),
                "elevation": ("FLOAT", {"default": 0.0, "min": -60.0,
                                        "max": 60.0, "step": 5.0}),
                "distance": ("FLOAT", {"default": 1.0, "min": 0.6, "max": 1.8,
                                       "step": 0.1}),
                "extra_prompt": ("STRING", {"default": "", "multiline": True}),
            }
        }

    # MESMO contrato do no publicado, na mesma ordem: assim ele entra no lugar
    # dele no grafo sem mexer em mais nada.
    RETURN_TYPES = ("IMAGE", "IMAGE", "STRING", "INT", "INT")
    RETURN_NAMES = ("source", "target_normal", "prompt", "width", "height")
    FUNCTION = "preparar"
    CATEGORY = "Krea2/Anygles"
    DESCRIPTION = ("Gira a camera em torno da malha vinda do SAM 3D Body "
                   "nativo e renderiza o mapa alinhado que o LoRA consome.")

    def preparar(self, source, mhr_pose_data, yaw, elevation, distance,
                 extra_prompt):
        origem = _para_pil(source)
        largura, altura = _anygles.canvas_size(origem)
        origem = origem.resize((largura, altura), Image.Resampling.LANCZOS)

        pessoa = self._uma_pessoa(mhr_pose_data)
        faces = np.asarray(mhr_pose_data["faces"])

        keypoints = np.asarray(pessoa["pred_keypoints_3d"], dtype=np.float32)
        vertices = np.asarray(pessoa["pred_vertices"], dtype=np.float32)
        camera_base = np.asarray(pessoa["pred_cam_t"], dtype=np.float32).reshape(3)
        focal = float(np.asarray(pessoa["focal_length"]).reshape(-1)[0])

        # A ORDEM importa e e a deles: primeiro guinada, depois elevacao, as
        # duas em torno da pelve (media dos keypoints 9 e 10). Inverter da uma
        # pose parecida e errada, porque a elevacao passaria a girar em torno
        # de um eixo que a guinada ja mexeu.
        vt = _normal._rotate_yaw(vertices, keypoints, yaw)
        vt = _normal._rotate_elevation(vt, keypoints, elevation)

        base = _normal._project(vt, camera_base, focal, largura, altura)
        escala = _normal._base_fit(base, largura, altura)
        camera = camera_base.copy()
        camera[2] *= np.float32(distance)
        projetado = _normal._project(vt, camera, focal, largura, altura)
        centrado = (projetado - np.array([largura / 2, altura / 2])) * escala
        deslocamento = -(centrado.min(0) + centrado.max(0)) * 0.5

        normal = _renderiza_fora(vt, faces, camera, focal, largura, altura,
                                 escala, deslocamento)
        return (_para_tensor(origem), _para_tensor(normal),
                _anygles.camera_prompt(float(yaw), float(elevation),
                                       float(distance), extra_prompt),
                largura, altura)

    @staticmethod
    def _uma_pessoa(dados):
        """O nativo entrega quadros x pessoas; o Anygles trata UMA pessoa.

        Falhar aqui com uma frase clara e melhor que seguir com a primeira
        deteccao: numa foto com duas pessoas o resultado sairia girando a
        errada, e isso passa por "o modelo nao entendeu".
        """
        quadros = dados.get("frames") or []
        com_gente = [q for q in quadros if q]
        if not com_gente:
            raise ValueError("o SAM 3D Body nao achou ninguem nesta imagem")
        pessoas = com_gente[0]
        if len(pessoas) != 1:
            raise ValueError(
                "o Anygles gira UMA pessoa, e foram detectadas %d — recorte a "
                "imagem, ou limite a caixa de deteccao a uma" % len(pessoas))
        return pessoas[0]


NODE_CLASS_MAPPINGS = {"Krea2AnyglesCameraNativo": Krea2AnyglesCameraNativo}
NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2AnyglesCameraNativo": "Krea2 Anygles Camera (SAM3D nativo)"
}
