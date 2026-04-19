import axios from 'axios';

const BASE = import.meta.env.VITE_API_BASE || '/api';

const client = axios.create({ baseURL: BASE });

export const listS3Files = (bucket) =>
  client.get('/s3/files/', { params: { bucket } });

export const processFile = (bucket, fileKey, typeOverrides = {}) =>
  client.post('/process/', {
    bucket,
    file_key: fileKey,
    type_overrides: typeOverrides,
  });

export const getHistory = () => client.get('/history/');
