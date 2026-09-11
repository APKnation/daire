const backendPort = process.env.BACKEND_PORT || '8081';

module.exports = {
  '/api': {
    target: `http://127.0.0.1:${backendPort}`,
    secure: false,
    changeOrigin: true,
  },
};
