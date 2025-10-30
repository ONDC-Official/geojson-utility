FROM node:20-alpine AS builder
WORKDIR /app
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY . .
RUN echo "VITE_API_BASE_URL=$VITE_API_BASE_URL" > .env.production
RUN npm install
RUN npm run build

FROM node:18-slim
WORKDIR /app

RUN npm install -g serve
COPY --from=builder /app/dist /app/dist
EXPOSE 80
CMD ["serve", "-s", "dist", "-l", "5001"]
