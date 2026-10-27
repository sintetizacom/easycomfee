// Estudios por modelo (MiniMax H3, Wan, FLUX 3), no mesmo desenho do LTX
// Studio: uma capa e cartoes de atalho. Cada cartao abre a aba certa ja com o
// modo e o modelo escolhidos ("#video/imagem/minimax"; ver parteDoHash).

type Fluxo = { nome: string; descricao: string; destino: string; etiqueta: string }
type Secao = { numero: string; titulo: string; texto: string; fluxos: Fluxo[] }
type Estudio = {
  sobretitulo: string; titulo: string; texto: string
  destaque: { rotulo: string; destino: string }
  capa: string  // .mp4 toca em loop; o resto e imagem
  secoes: Secao[]
}

function Cartao({ fluxo }: { fluxo: Fluxo }) {
  return (
    <a className="hf-ltx-cartao" href={fluxo.destino}>
      <span className="hf-ltx-etiqueta">{fluxo.etiqueta}</span>
      <strong>{fluxo.nome}</strong>
      <span>{fluxo.descricao}</span>
      <b aria-hidden="true">↗</b>
    </a>
  )
}

function PaginaEstudio({ e }: { e: Estudio }) {
  return (
    <div className="hf-aba hf-ltx">
      <div className="hf-ltx-capa">
        <div>
          <span className="hf-sobretitulo">{e.sobretitulo}</span>
          <h1>{e.titulo}</h1>
          <p>{e.texto}</p>
          <a className="hf-ltx-destaque" href={e.destaque.destino}>{e.destaque.rotulo} <span aria-hidden="true">↗</span></a>
        </div>
        {e.capa.endsWith('.mp4')
          ? <video src={e.capa} muted loop autoPlay playsInline aria-hidden="true" />
          : <img src={e.capa} alt="" aria-hidden="true" className="hf-ltx-capa-img" />}
      </div>
      {e.secoes.map((s) => (
        <section key={s.numero} className="hf-ltx-secao">
          <div className="hf-ltx-cabecalho"><span>{s.numero}</span><h2>{s.titulo}</h2><p>{s.texto}</p></div>
          <div className="hf-ltx-grade">{s.fluxos.map((f) => <Cartao key={f.nome + f.destino} fluxo={f} />)}</div>
        </section>
      ))}
    </div>
  )
}

const H3: Estudio = {
  sobretitulo: 'MINIMAX H3 · OPEN WEIGHTS · VIDEO WITH SOUND',
  titulo: 'Video with sound, characters and music.',
  texto: 'MiniMax H3 makes video and its soundtrack together. Run the open model on a big GPU, the fast distilled FastH3, or Comfy Cloud.',
  destaque: { rotulo: 'Start with Image → Video', destino: '#video/imagem/minimax' },
  capa: '/exemplos/capa_h3.mp4',
  secoes: [
    { numero: '01 / CREATE', titulo: 'Make the shot', texto: 'Text, a first frame, or how the shot begins and ends.', fluxos: [
      { nome: 'Text → Video', descricao: 'A scene from a line of text, with sound.', destino: '#video/texto/minimax', etiqueta: 'MiniMax H3' },
      { nome: 'Image → Video', descricao: 'Animate a still, keeping its subject and look.', destino: '#video/imagem/minimax', etiqueta: 'MiniMax H3' },
      { nome: 'First & last frame', descricao: 'Choose how the shot begins and ends.', destino: '#video/primeiro_ultimo/minimax', etiqueta: 'MiniMax H3' },
      { nome: 'FastH3', descricao: 'MiniMax H3 distilled to 8 steps: the same model, about twice as fast, up to 15 s.', destino: '#video/texto/fasth3', etiqueta: 'Local GPU · 8 steps' },
      { nome: 'References → Video', descricao: 'Put up to 9 people or objects from your images into one shot.', destino: '#video/referencia/minimax-ref-nuvem', etiqueta: 'Comfy Cloud · API' },
    ] },
    { numero: '02 / RECAST', titulo: 'Swap the character', texto: 'Keep the motion, camera, light and sound of a video; change who is in it.', fluxos: [
      { nome: 'H3 Character Swap', descricao: 'SAM 3 finds who to replace; MiniMax H3 puts your character in, with the original motion and sound.', destino: '#genjutsu/h3_swap', etiqueta: 'MiniMax H3 Ref2VA' },
    ] },
    { numero: '03 / SOUND', titulo: 'Score it', texto: 'The same family writes the music.', fluxos: [
      { nome: 'MiniMax Music 3', descricao: 'Full songs with vocals and lyrics, up to 5 minutes.', destino: '#music/minimax-music3', etiqueta: 'MiniMax Music 3' },
    ] },
  ],
}

const WAN: Estudio = {
  sobretitulo: 'WAN · OPEN WEIGHTS · VIDEO + CHARACTER ANIMATION',
  titulo: 'From a tiny GPU to a full studio.',
  texto: 'Alibaba’s Wan family, from the 1.3B model that runs on 8 GB to Wan 2.2 14B, plus character animation that copies the motion of any video.',
  destaque: { rotulo: 'Animate a character', destino: '#genjutsu/wan_animate2' },
  capa: '/exemplos/capa_wan.mp4',
  secoes: [
    { numero: '01 / CREATE', titulo: 'Make the shot', texto: 'Pick the size that fits your graphics card, or run it on Comfy Cloud.', fluxos: [
      { nome: 'Text → Video', descricao: 'Wan 2.2 14B in 4 steps (lightx2v), from the official ComfyUI template.', destino: '#video/texto/wan22_14b', etiqueta: 'Wan 2.2 14B' },
      { nome: 'Image → Video', descricao: 'Animate a still with Wan 2.2 14B.', destino: '#video/imagem/wan22_14b', etiqueta: 'Wan 2.2 14B' },
      { nome: 'First & last frame', descricao: 'Wan 2.2 14B moves from one image to another.', destino: '#video/primeiro_ultimo/wan22_14b', etiqueta: 'Wan 2.2 14B' },
      { nome: 'Wan 2.2 5B', descricao: 'Text or image to 720p video on an 8 GB card.', destino: '#video/texto/wan22_5b', etiqueta: 'Light · 8 GB' },
      { nome: 'Wan 2.1 1.3B', descricao: 'The lightest Wan: text to 480p video.', destino: '#video/texto/wan21_13b', etiqueta: 'Light · 8 GB' },
      { nome: 'Wan 3.0', descricao: 'Image, first & last frame and references, hosted by Comfy.', destino: '#video/imagem/wan3', etiqueta: 'Comfy Cloud · API' },
      { nome: 'Wan 2.7', descricao: 'Text, image and first & last frame, hosted by Comfy.', destino: '#video/texto/wan27', etiqueta: 'Comfy Cloud · API' },
    ] },
    { numero: '02 / ANIMATE', titulo: 'Bring a character to life', texto: 'Copy the exact motion of a video: face, body and hands.', fluxos: [
      { nome: 'Wan Animate 2', descricao: 'The person in your photo performs the video’s motion, in the photo’s own setting.', destino: '#genjutsu/wan_animate2', etiqueta: 'Comfy Cloud' },
      { nome: 'Wan 2.2 Animate · Replace', descricao: 'Your character replaces the person inside the video; the light is matched to the scene.', destino: '#genjutsu/wan22_replace', etiqueta: 'Wan 2.2 Animate' },
    ] },
    { numero: '03 / IMAGE', titulo: 'Make the still', texto: 'A first frame for any of the above.', fluxos: [
      { nome: 'Wan 2.5 Image', descricao: 'Text to image with Wan 2.5.', destino: '#image/wan25img', etiqueta: 'Comfy Cloud · API' },
    ] },
  ],
}

const FLUX3: Estudio = {
  sobretitulo: 'FLUX 3 · BLACK FOREST LABS · IMAGE + VIDEO',
  titulo: 'Photoreal images, edits and video.',
  texto: 'FLUX 3 Klein runs on your own GPU; the full FLUX 3 and FLUX 3 Video run on Comfy Cloud. Edit with reference images, direct a shot, then animate it.',
  destaque: { rotulo: 'Create with Flux 3 Klein', destino: '#image/flux3' },
  capa: '/exemplos/capa_flux3.webp?v=2',
  secoes: [
    { numero: '01 / IMAGE', titulo: 'Make the picture', texto: 'From a sentence, or from your own images as references.', fluxos: [
      { nome: 'Flux 3 Klein', descricao: 'Photorealism and well-written text, on your GPU or on Comfy Cloud.', destino: '#image/flux3', etiqueta: 'FLUX 3 Klein' },
      { nome: 'Edit with references', descricao: 'Drop images into the box and describe the change: @image1, @image2…', destino: '#image/flux3', etiqueta: 'FLUX 3 Klein' },
      { nome: 'FLUX 3', descricao: 'The full FLUX 3 model, hosted by Comfy.', destino: '#image/flux3api', etiqueta: 'Comfy Cloud · API' },
      { nome: 'Cinema Studio', descricao: 'Direct the shot: camera, lens, light, film and grade, with Flux 3 Klein.', destino: '#cinema', etiqueta: 'FLUX 3 Klein' },
    ] },
    { numero: '02 / VIDEO', titulo: 'Move it', texto: 'Animate a FLUX 3 picture, or go straight to video.', fluxos: [
      { nome: 'FLUX 3 Video', descricao: 'Text or image to video.', destino: '#video/texto/flux3video', etiqueta: 'Comfy Cloud · API' },
      { nome: 'FLUX 3 Max Video', descricao: 'The highest-quality FLUX video.', destino: '#video/texto/flux3max', etiqueta: 'Comfy Cloud · API' },
      { nome: 'Animate a FLUX 3 picture', descricao: 'Hover any image in the gallery and press ▶ Animate: LTX moves it, with sound.', destino: '#video/imagem', etiqueta: 'FLUX 3 + LTX' },
    ] },
    { numero: '03 / THE FLUX FAMILY', titulo: 'More FLUX, open weights', texto: 'Other FLUX models you can install from Config Models.', fluxos: [
      { nome: 'FLUX 2 Klein 9B', descricao: 'Maximum micro-detail and texture.', destino: '#image/klein', etiqueta: 'FLUX 2' },
      { nome: 'FLUX.2 dev', descricao: 'The big FLUX.2 (32B). Best on Comfy Cloud.', destino: '#image/flux2dev', etiqueta: 'FLUX 2' },
      { nome: 'FLUX.1 Krea dev', descricao: 'Natural photos that look less like AI.', destino: '#image/flux1krea', etiqueta: 'FLUX.1' },
      { nome: 'FLUX.1 schnell', descricao: 'Fast and light: 4 steps, 8–12 GB cards.', destino: '#image/flux1s', etiqueta: 'FLUX.1' },
    ] },
  ],
}

export const AbaH3 = () => <PaginaEstudio e={H3} />
export const AbaWan = () => <PaginaEstudio e={WAN} />
export const AbaFlux3 = () => <PaginaEstudio e={FLUX3} />
