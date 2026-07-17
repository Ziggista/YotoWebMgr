FROM node:20-alpine

ARG VITE_APP_BUILD_SHA=dev

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html tsconfig.json tsconfig.app.json vite.config.ts ./
COPY public ./public
COPY src ./src

ENV VITE_APP_BUILD_SHA=${VITE_APP_BUILD_SHA}

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
