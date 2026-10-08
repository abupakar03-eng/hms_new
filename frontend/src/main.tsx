import React from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import App from './App.tsx'
import { api } from './api'
import { ErrorBoundary } from './ui/ErrorBoundary'
import { DialogHost, RequestProgress, Toaster, trackRequests } from './ui/feedback'
import './index.css'

// Both HTTP clients feed the global activity bar.
trackRequests(axios)
trackRequests(api)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <RequestProgress />
      <App />
      <Toaster />
      <DialogHost />
    </ErrorBoundary>
  </React.StrictMode>,
)
