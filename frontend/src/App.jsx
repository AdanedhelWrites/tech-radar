import { Routes, Route, NavLink, Link } from 'react-router-dom'
import { Navbar, Nav, Container } from 'react-bootstrap'
import { FaNewspaper, FaShieldAlt, FaDharmachakra, FaServer, FaToolbox, FaRobot } from 'react-icons/fa'
import NewsComponent from './components/NewsComponent'
import CVEComponent from './components/CVEComponent'
import KubernetesComponent from './components/KubernetesComponent'
import SREComponent from './components/SREComponent'
import DevToolsComponent from './components/DevToolsComponent'
import AINewsComponent from './components/AINewsComponent'
import SaglikSeridi from './components/SaglikSeridi'
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
          <Route path="/" element={<HomePage />} />
          <Route path="/news" element={<NewsComponent />} />
          <Route path="/cve" element={<CVEComponent />} />
          <Route path="/k8s" element={<KubernetesComponent />} />
          <Route path="/sre" element={<SREComponent />} />
          <Route path="/devtools" element={<DevToolsComponent />} />
          <Route path="/ai" element={<AINewsComponent />} />
        </Routes>
      </Container>
    </div>
  )
}

// Gecici: Task 6 bu sayfayi Genel Bakis panosuyla degistirir
function HomePage() {
  return (
    <div className="text-center py-5">
      <h1 className="display-4 mb-4">Teknoloji Radar</h1>
      <p className="lead mb-5">
        Güncel siber güvenlik haberleri, CVE (Common Vulnerabilities and Exposures),
        Kubernetes, SRE (Site Reliability Engineering) ve DevTools altyapı araçları güncellemelerini tek bir yerden takip edin.
      </p>
      <SaglikSeridi />

      <div className="row justify-content-center">
        <div className="col-md-3 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaNewspaper size={48} className="text-primary mb-3" />
              <h5 className="card-title">Siber Güvenlik</h5>
              <p className="card-text">
                12 kaynaktan siber güvenlik haberlerini çekin, Türkçeye çevrilmiş
                tam makale içeriklerini okuyun ve HTML rapor olarak indirin.
              </p>
              <NavLink to="/news" className="btn btn-primary">
                Haberleri Görüntüle
              </NavLink>
            </div>
          </div>
        </div>

        <div className="col-md-3 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaShieldAlt size={48} className="text-danger mb-3" />
              <h5 className="card-title">CVE Zafiyetleri</h5>
              <p className="card-text">
                5 kaynaktan (CISA KEV dahil) güncel CVE zafiyetlerini çekin, CVSS şiddet seviyesine
                göre filtreleyin ve Türkçe açıklamalarını okuyun.
              </p>
              <NavLink to="/cve" className="btn btn-danger">
                Zafiyetleri Görüntüle
              </NavLink>
            </div>
          </div>
        </div>

        <div className="col-md-3 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaDharmachakra size={48} className="text-info mb-3" />
              <h5 className="card-title">Kubernetes</h5>
              <p className="card-text">
                3 kaynaktan Kubernetes blog yazılarını, release notlarını ve
                CNCF haberlerini çekin, Türkçe olarak takip edin.
              </p>
              <NavLink to="/k8s" className="btn btn-info text-white">
                Haberleri Görüntüle
              </NavLink>
            </div>
          </div>
        </div>

        <div className="col-md-3 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaServer size={48} className="text-success mb-3" />
              <h5 className="card-title">SRE</h5>
              <p className="card-text">
                5 kaynaktan Site Reliability Engineering haberlerini çekin,
                incident management ve DevOps içeriklerini Türkçe okuyun.
              </p>
              <NavLink to="/sre" className="btn btn-success">
                Haberleri Görüntüle
              </NavLink>
            </div>
          </div>
        </div>
      </div>

      <div className="row justify-content-center mt-2">
        <div className="col-md-4 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaToolbox size={48} className="mb-3" style={{ color: '#e67e22' }} />
              <h5 className="card-title">DevTools</h5>
              <p className="card-text">
                13 kaynaktan altyapı araçları güncellemelerini çekin — PostgreSQL, MongoDB,
                Redis, Elasticsearch, RabbitMQ, Ceph, Seq, Moodle, LiteLLM, LangGraph,
                Langfuse, GitLab ve Keycloak.
              </p>
              <NavLink to="/devtools" className="btn" style={{ backgroundColor: '#e67e22', color: '#fff' }}>
                Güncellemeleri Görüntüle
              </NavLink>
            </div>
          </div>
        </div>

        <div className="col-md-4 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaRobot size={48} className="mb-3" style={{ color: '#8e44ad' }} />
              <h5 className="card-title">Yapay Zeka (AI)</h5>
              <p className="card-text">
                Popüler yapay zeka ve LLM gelişmeleri ile benchmark haberlerini, güncel AI kaynaklarından takip edin ve Türkçe okuyun.
              </p>
              <NavLink to="/ai" className="btn" style={{ backgroundColor: '#8e44ad', color: '#fff' }}>
                Gelişmeleri Gör
              </NavLink>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
