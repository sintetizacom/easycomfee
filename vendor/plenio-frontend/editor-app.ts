// Entrada do EasyComfee: expoe so o editor da Song Sheet do Plenio
// (v1.0.2, Apache-2.0, ver LICENSE e NOTICE.md) como window.PlenioSheet, para
// a aba Musica (React) abrir sem o ComfyUI. Nada daqui depende do grafo.
import { openSheetDialog } from './src/sheet-editor/open'
import { parseGuide } from './src/sheet-editor/score/tracks'

declare global {
  interface Window { PlenioSheet: { openSheetDialog: typeof openSheetDialog; parseGuide: typeof parseGuide } }
}
window.PlenioSheet = { openSheetDialog, parseGuide }
