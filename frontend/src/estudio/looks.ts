// One-tap looks da aba Image: prompts prontos que embrulham o assunto que a
// pessoa digitou ({s}). Nomes e textos proprios do EasyComfee. Testados no
// Flux 3 Klein local em 27/10/2026.
export type Look = { id: string; rotulo: string; exemplo: string; texto: string }

export const LOOKS: Look[] = [
  { id: 'poster', rotulo: 'Gallery Poster', exemplo: 'a lighthouse at dawn',
    texto: 'A bold minimalist art poster of {s}, flat graphic shapes, limited three-color palette, generous empty margins, screen-print texture, museum gift shop quality' },
  { id: 'packshot', rotulo: 'Studio Packshot', exemplo: 'a glass perfume bottle',
    texto: 'A clean commercial product photograph of {s} on a seamless pastel backdrop, large softbox lighting, crisp reflections, centered composition, high-end catalog look' },
  { id: 'headshot', rotulo: 'Pro Headshot', exemplo: 'a smiling woman in her thirties',
    texto: 'A professional headshot of {s}, soft window light from the side, plain warm-grey backdrop, shallow depth of field, natural skin texture, business casual' },
  { id: 'comic', rotulo: 'Ink & Panels', exemplo: 'a detective in a trench coat on a rooftop at night',
    texto: 'A single classic comic book panel of {s}, expressive human faces, bold black ink outlines, halftone dot shading, dramatic angle, vivid flat colors' },
  { id: 'argila', rotulo: 'Clay Buddy', exemplo: 'a fox wearing a scarf',
    texto: '{s} as a cute handmade clay figurine, soft rounded shapes, tiny fingerprints in the clay, tabletop miniature photo, warm afternoon light' },
  { id: 'pixel', rotulo: '16-bit Quest', exemplo: 'a knight crossing a bridge',
    texto: '{s} as a 16-bit pixel art video game scene, crisp square pixels, limited palette, side-scrolling view, retro console look' },
  { id: 'miniatura', rotulo: 'Tiny World', exemplo: 'a busy city square',
    texto: 'A tilt-shift photograph of {s} that looks like a toy miniature diorama, tiny scale, strong shallow focus at top and bottom, bright saturated daylight' },
  { id: 'papel', rotulo: 'Paper Layers', exemplo: 'a forest with a deer',
    texto: '{s} made of layered colored paper cutouts, papercraft depth, soft shadows between the paper layers, gentle pastel colors' },
  { id: 'neon', rotulo: 'Neon Glow', exemplo: 'a coffee cup',
    texto: '{s} drawn as a glowing neon sign mounted on a dark brick wall, bent glass tubes, colored light bloom on the bricks, night' },
  { id: 'postal', rotulo: 'Retro Postcard', exemplo: 'a beach town',
    texto: 'A vintage 1960s travel postcard illustration of {s}, faded printed colors, sunny optimism, subtle paper texture and grain, no text or lettering' },
  { id: 'planta', rotulo: 'Blueprint', exemplo: 'a vintage motorcycle',
    texto: 'A technical blueprint drawing of {s}, thin white lines on deep blue paper, measurement lines, construction grid, engineering style' },
  { id: 'adesivo', rotulo: 'Sticker Sheet', exemplo: 'a happy avocado',
    texto: 'A sheet of glossy die-cut stickers of {s} in different poses, thick white borders, playful cartoon style, plain light background' },
]

/** O prompt final: o look em volta do assunto (ou do exemplo, se a caixa estiver vazia). */
export const aplicarLook = (look: Look | undefined, assunto: string) =>
  look ? look.texto.replace('{s}', assunto.trim() || look.exemplo) : assunto
