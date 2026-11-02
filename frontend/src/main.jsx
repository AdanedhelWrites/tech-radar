import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// Sira onemli: Bootstrap, ustune tema token'lari, en son uygulama stilleri (App.css)
import 'bootstrap/dist/css/bootstrap.min.css'
import './styles/tema.css'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
