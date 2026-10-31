// Vitest kurulumu: jest-dom eslestiricileri (toBeInTheDocument, toBeEmptyDOMElement...)
import '@testing-library/jest-dom/vitest'

// jsdom matchMedia saglamaz; react-bootstrap Offcanvas (okuma paneli) useBreakpoint ile onu cagirir.
// Hicbir medya sorgusu eslesmez: masaustu genisligi varsayilir.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })
}
