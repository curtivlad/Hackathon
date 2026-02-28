FROM node:20-alpine

WORKDIR /app

ARG VITE_API_TOKEN=v2x-secret-token-change-in-prod
ENV VITE_API_TOKEN=${VITE_API_TOKEN}

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

EXPOSE 3000

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "3000"]
