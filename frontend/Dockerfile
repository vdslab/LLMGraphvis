FROM node:24.22.3-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS build
COPY . .
RUN npm run build

FROM dependencies AS development
COPY . .
CMD ["npm", "run", "dev", "--", "--host"]
