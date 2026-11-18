FROM node:20-alpine AS builder

WORKDIR /app

COPY web/package*.json ./

RUN npm ci || npm install

COPY web/ ./

RUN npm run build


FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app ./

EXPOSE 3000

CMD ["npm", "run", "start"]
