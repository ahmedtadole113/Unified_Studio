import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://portal-backend:8000',
        changeOrigin: true
      },
      '/minio-api': {
        target: 'http://minio:9001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio-api/, ''),
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            delete proxyRes.headers['x-frame-options'];
            delete proxyRes.headers['content-security-policy'];
          });
        }
      },
      '/services/datalake': {
        target: 'http://minio:9001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/services\/datalake/, ''),
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            delete proxyRes.headers['x-frame-options'];
            delete proxyRes.headers['content-security-policy'];
          });
        }
      },
      '/services/databricks': {
        target: 'http://spark-processing:8888',
        changeOrigin: true,
        ws: true
      },
      '/services/airflow': {
        target: 'http://airflow-webserver:8080',
        changeOrigin: true
      },
      '/services/synapse': {
        target: 'http://pgadmin:80',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            proxyReq.setHeader('X-Script-Name', '/services/synapse');
          });
          proxy.on('proxyRes', (proxyRes) => {
            delete proxyRes.headers['x-frame-options'];
            delete proxyRes.headers['content-security-policy'];
          });
        }
      },
      '/services/eventhub': {
        target: 'http://redpanda-console:8080',
        changeOrigin: true
      },
      '/services/servicebus': {
        target: 'http://rabbitmq:15672',
        changeOrigin: true
      },
      '/services/monitoring': {
        target: 'http://grafana:3000',
        changeOrigin: true
      },
      '/services/prometheus': {
        target: 'http://prometheus:9090',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/services\/prometheus/, '')
      }
    }
  }
})
