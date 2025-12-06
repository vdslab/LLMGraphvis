FROM node:18-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

CMD ["sh", "-c", "npm install && npm run dev -- --host"]
