FROM node:20-alpine

ARG VITE_APP_BUILD_SHA=dev
ARG VITE_APP_VERSION_NAME=v0.1b0001
ARG VITE_APP_VERSION_CODE=1

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html tsconfig.json tsconfig.app.json vite.config.ts ./
COPY public ./public
COPY src ./src

ENV VITE_APP_BUILD_SHA=${VITE_APP_BUILD_SHA}
ENV VITE_APP_VERSION_NAME=${VITE_APP_VERSION_NAME}
ENV VITE_APP_VERSION_CODE=${VITE_APP_VERSION_CODE}

EXPOSE 5173

CMD ["npm", "--silent", "run", "dev", "--", "--host", "0.0.0.0"]
