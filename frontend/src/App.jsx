import { useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { Navbar, Nav, Container } from 'react-bootstrap'
import { FaNewspaper, FaShieldAlt, FaHome, FaDharmachakra, FaSun, FaMoon, FaTree, FaServer, FaToolbox, FaRobot } from 'react-icons/fa'
import NewsComponent from './components/NewsComponent'
import CVEComponent from './components/CVEComponent'
import KubernetesComponent from './components/KubernetesComponent'
import SREComponent from './components/SREComponent'
import DevToolsComponent from './components/DevToolsComponent'
import AINewsComponent from './components/AINewsComponent'
import { Toaster } from 'react-hot-toast'
import './App.css'

function App() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : false
  })

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
    document.body.setAttribute('data-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  return (
    <div className={`App ${darkMode ? 'dark-mode' : 'light-mode'}`}>
      <Toaster position="bottom-right" toastOptions={{ duration: 4000 }} />
      <Navbar bg="dark" variant="dark" expand="lg" className="mb-4">
        <Container>
          <Navbar.Brand href="/">
            <FaTree className="me-2" />
            Teknoloji Radar
          </Navbar.Brand>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav">
            <Nav className="me-auto">
              <Nav.Link as={NavLink} to="/" end>
                <FaHome className="me-1" /> Ana Sayfa
              </Nav.Link>
              <Nav.Link as={NavLink} to="/news">
                <FaNewspaper className="me-1" /> Siber Güvenlik
              </Nav.Link>
              <Nav.Link as={NavLink} to="/cve">
                <FaShieldAlt className="me-1" /> CVE
              </Nav.Link>
              <Nav.Link as={NavLink} to="/k8s">
                <FaDharmachakra className="me-1" /> Kubernetes
              </Nav.Link>
              <Nav.Link as={NavLink} to="/sre">
                <FaServer className="me-1" /> SRE
              </Nav.Link>
              <Nav.Link as={NavLink} to="/devtools">
                <FaToolbox className="me-1" /> DevTools
              </Nav.Link>
              <Nav.Link as={NavLink} to="/ai">
                <FaRobot className="me-1" /> Yapay Zeka
              </Nav.Link>
            </Nav>
            <button
              className="theme-toggle-icon"
              onClick={() => setDarkMode(!darkMode)}
              title={darkMode ? 'Aydınlık Mod' : 'Karanlık Mod'}
              aria-label={darkMode ? 'Aydınlık Mod' : 'Karanlık Mod'}
            >
              {darkMode ? <FaSun /> : <FaMoon />}
            </button>
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

function HomePage() {
  return (
    <div className="text-center py-5">
      <h1 className="display-4 mb-4">Teknoloji Radar</h1>
      <p className="lead mb-5">
        Güncel siber güvenlik haberleri, CVE (Common Vulnerabilities and Exposures),
        Kubernetes, SRE (Site Reliability Engineering) ve DevTools altyapı araçları güncellemelerini tek bir yerden takip edin.
      </p>

      <div className="row justify-content-center">
        <div className="col-md-3 mb-4">
          <div className="card h-100 shadow-sm">
            <div className="card-body">
              <FaNewspaper size={48} className="text-primary mb-3" />
              <h5 className="card-title">Siber Güvenlik</h5>
              <p className="card-text">
                5 kaynaktan siber güvenlik haberlerini çekin, Türkçeye çevrilmiş
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
                5 kaynaktan güncel CVE zafiyetlerini çekin, CVSS şiddet seviyesine
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
                9 kaynaktan altyapı araçları güncellemelerini çekin — MinIO, PostgreSQL,
                MongoDB, Redis, Elasticsearch, RabbitMQ, Ceph, Seq ve Moodle.
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
