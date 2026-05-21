FROM node:22-alpine

WORKDIR /app

COPY package*.json /app/
RUN npm install

COPY . /app

CMD ["sh", "-c", "npm run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT:-5173}"]
