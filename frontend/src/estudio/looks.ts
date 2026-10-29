// One-tap looks da aba Image: prompts prontos que embrulham o assunto que a
// pessoa digitou ({s}). Nomes e textos proprios do EasyComfee. Testados no
// Flux 3 Klein local em 27/10/2026.
// comImagem: o look transforma a foto enviada (@image1) em vez de criar do zero.
// foto: a versao do look para quando ha uma foto na caixa (transforma a foto em vez de criar do zero).
export type Look = { id: string; rotulo: string; exemplo: string; texto: string; foto?: string; comImagem?: boolean }

export const LOOKS: Look[] = [
  { id: 'poster', rotulo: 'Gallery Poster', exemplo: 'a lighthouse at dawn',
    texto: 'A bold minimalist art poster of {s}, flat graphic shapes, limited three-color palette, generous empty margins, screen-print texture, museum gift shop quality',
    foto: 'Make a bold minimalist art poster of the subject from @image1: flat graphic shapes, limited three-color palette, generous empty margins, screen-print texture, museum gift shop quality. {s}' },
  { id: 'packshot', rotulo: 'Studio Packshot', exemplo: 'a glass perfume bottle',
    texto: 'A clean commercial product photograph of {s} on a seamless pastel backdrop, large softbox lighting, crisp reflections, centered composition, high-end catalog look',
    foto: 'Place the main object from @image1 in a clean commercial product photograph on a seamless pastel backdrop, large softbox lighting, crisp reflections, centered composition, high-end catalog look. {s}' },
  { id: 'headshot', rotulo: 'Pro Headshot', exemplo: 'a smiling woman in her thirties',
    texto: 'A professional headshot of {s}, soft window light from the side, plain warm-grey backdrop, shallow depth of field, natural skin texture, business casual',
    foto: 'Turn the person from @image1 into a professional headshot, keeping the same face and identity: soft window light from the side, plain warm-grey backdrop, shallow depth of field, business casual, natural skin texture. {s}' },
  { id: 'comic', rotulo: 'Ink & Panels', exemplo: 'a detective in a trench coat on a rooftop at night',
    texto: 'A single classic comic book panel of {s}, expressive human faces, bold black ink outlines, halftone dot shading, dramatic angle, vivid flat colors',
    foto: 'Redraw @image1 as a single classic comic book panel with only the people from the photo, no extra characters: same pose and clothes, expressive face, bold black ink outlines, halftone dot shading, vivid flat colors. {s}' },
  { id: 'argila', rotulo: 'Clay Buddy', exemplo: 'a fox wearing a scarf',
    texto: '{s} as a cute handmade clay figurine, soft rounded shapes, tiny fingerprints in the clay, tabletop miniature photo, warm afternoon light',
    foto: 'Recreate the person from @image1 as a cute handmade clay figurine: same hair color and hairstyle, same clothes and colors, same face shape, soft rounded clay shapes with tiny fingerprints, standing on a wooden table, tabletop miniature photo, warm light. {s}' },
  { id: 'pixel', rotulo: '16-bit Quest', exemplo: 'a knight crossing a bridge',
    texto: '{s} as a 16-bit pixel art video game scene, crisp square pixels, limited palette, side-scrolling view, retro console look',
    foto: 'Redraw @image1 as a 16-bit pixel art video game scene with the same subject: crisp square pixels, limited palette, retro console look. {s}' },
  { id: 'miniatura', rotulo: 'Tiny World', exemplo: 'a busy city square',
    texto: 'A tilt-shift photograph of {s} that looks like a toy miniature diorama, tiny scale, strong shallow focus at top and bottom, bright saturated daylight',
    foto: 'Turn @image1 into a toy miniature diorama: the person becomes a tiny painted figurine with the same hair and clothes, standing in a miniature model of the scene, tilt-shift photo with strong shallow focus at top and bottom, bright saturated colors. {s}' },
  { id: 'papel', rotulo: 'Paper Layers', exemplo: 'a forest with a deer',
    texto: '{s} made of layered colored paper cutouts, papercraft depth, soft shadows between the paper layers, gentle pastel colors',
    foto: 'Recreate the person from @image1 entirely out of layered colored paper cutouts, including the face with paper eyes, nose and mouth, same hair color and clothes colors, papercraft depth, soft shadows between the paper layers. {s}' },
  { id: 'neon', rotulo: 'Neon Glow', exemplo: 'a coffee cup',
    texto: '{s} drawn as a glowing neon sign mounted on a dark brick wall, bent glass tubes, colored light bloom on the bricks, night',
    foto: 'Turn the subject from @image1 into a glowing neon sign mounted on a dark brick wall, bent glass tubes tracing its outline, colored light bloom on the bricks, night. {s}' },
  { id: 'postal', rotulo: 'Retro Postcard', exemplo: 'a beach town',
    texto: 'A vintage 1960s travel postcard illustration of {s}, faded printed colors, sunny optimism, subtle paper texture and grain, no text or lettering',
    foto: 'Repaint @image1 as a vintage 1960s illustrated travel postcard: gouache painting style, simplified flat shapes, faded printed colors, white border, subtle paper texture and grain, same person and setting, no text or lettering. {s}' },
  { id: 'planta', rotulo: 'Blueprint', exemplo: 'a vintage motorcycle',
    texto: 'A technical blueprint drawing of {s}, thin white lines on deep blue paper, measurement lines, construction grid, engineering style',
    foto: 'Turn the subject of @image1 into a technical blueprint drawing: thin white lines on deep blue paper, measurement lines, construction grid, engineering style. {s}' },
  { id: 'adesivo', rotulo: 'Sticker Sheet', exemplo: 'a happy avocado',
    texto: 'A sheet of glossy die-cut stickers of {s} in different poses, thick white borders, playful cartoon style, plain light background',
    foto: 'Turn the subject from @image1 into a sheet of glossy die-cut cartoon stickers in different poses, thick white borders, plain light background. {s}' },
  { id: 'estatua', rotulo: 'Desk Figurine', exemplo: '', comImagem: true,
    texto: 'Turn the person from @image1 into a 1/7 scale collectible figurine statue, keeping the face, hair, outfit and pose. The figurine stands on a round clear acrylic base on a tidy wooden office desk, next to a computer monitor and keyboard, with a coffee mug nearby. Realistic product photo of a painted PVC figure, soft daylight from a window, shallow depth of field. {s}' },
]

/** O prompt final: o look em volta do assunto (ou do exemplo, se a caixa estiver vazia); com
 *  foto na caixa, a versao do look que transforma a foto (o texto vira um ajuste extra). */
export const aplicarLook = (look: Look | undefined, assunto: string, comFoto = false) =>
  !look ? assunto
    : comFoto && look.foto ? look.foto.replace('{s}', assunto.trim()).trim()
    : look.texto.replace('{s}', assunto.trim() || look.exemplo).trim()
