import { Routes, Route, NavLink, Link } from 'react-router-dom'
import { Navbar, Nav, Container } from 'react-bootstrap'
import NewsComponent from './components/NewsComponent'
import CVEComponent from './components/CVEComponent'
import KubernetesComponent from './components/KubernetesComponent'
import SREComponent from './components/SREComponent'
import DevToolsComponent from './components/DevToolsComponent'
import AINewsComponent from './components/AINewsComponent'
import GenelBakis from './components/genel/GenelBakis'
import { Toaster } from 'react-hot-toast'
import './App.css'

// Ust menu: tam adlar, spec G3 sirasi. Rotalar degismedi.
const MENU = [
  { ad: 'Genel Bakış', yol: '/' },
  { ad: 'Zafiyetler', yol: '/cve' },
  { ad: 'Siber Güvenlik', yol: '/news' },
  { ad: 'Kubernetes', yol: '/k8s' },
  { ad: 'SRE', yol: '/sre' },
  { ad: 'DevTools', yol: '/devtools' },
  { ad: 'Yapay Zeka', yol: '/ai' },
]

// Bildirimler koyu yuzeyde (react-hot-toast varsayilani beyaz)
const BILDIRIM_STILI = {
  background: 'var(--yuzey-yukseltilmis)',
  color: 'var(--metin)',
  border: '1px solid var(--cam-kenar)',
}

// Bilinmeyen adres (2026-11-07 inceleme): once yalniz menu cizilip icerik bos kaliyordu
function SayfaBulunamadi() {
  return (
    <section className="cam-kart sayfa-bulunamadi" aria-labelledby="bulunamadi-baslik">
      <h1 id="bulunamadi-baslik" className="sayfa-baslik">Sayfa bulunamadı</h1>
      <p>Aradığınız adres bu uygulamada yok. Menüden bir bölüm seçebilir ya da ana sayfaya dönebilirsiniz.</p>
      <Link to="/" className="cubuk-dugme birincil">Genel Bakış&apos;a dön</Link>
    </section>
  )
}

function App() {
  return (
    <div className="App">
      <Toaster position="bottom-right" toastOptions={{ duration: 4000, style: BILDIRIM_STILI }} />
      {/* role={null}: header kendiliginden "banner"; gezinme bolgesi icteki <nav> */}
      <Navbar as="header" role={null} expand="lg" collapseOnSelect className="ust-bant mb-4">
        <Container fluid className="px-4">
          <Navbar.Brand as={Link} to="/" className="marka">
            <span className="marka-logo" aria-hidden="true" />
            <span className="marka-adi">Teknoloji Radar</span>
            <small className="marka-alt d-none d-sm-inline">Tehdit ve Teknoloji İzleme</small>
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="ust-menu" label="Menüyü aç/kapat" />
          <Navbar.Collapse id="ust-menu">
            <Nav as="nav" aria-label="Ana menü" className="ust-menu ms-auto">
              {/* eventKey dar ekranda secimde menuyu kapatir (collapseOnSelect). active={false}:
                  aktiflik yalniz router NavLink'ten gelir; Nav'in ic durumu bayat kalmasin. */}
              {MENU.map(({ ad, yol }) => (
                <Nav.Link key={yol} as={NavLink} to={yol} eventKey={yol} active={false} end={yol === '/'}>
                  {ad}
                </Nav.Link>
              ))}
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>

      <Container fluid className="px-4">
        <Routes>
          <Route path="/" element={<GenelBakis />} />
          <Route path="/news" element={<NewsComponent />} />
          <Route path="/cve" element={<CVEComponent />} />
          <Route path="/k8s" element={<KubernetesComponent />} />
          <Route path="/sre" element={<SREComponent />} />
          <Route path="/devtools" element={<DevToolsComponent />} />
          <Route path="/ai" element={<AINewsComponent />} />
          <Route path="*" element={<SayfaBulunamadi />} />
        </Routes>
      </Container>
    </div>
  )
}

export default App
