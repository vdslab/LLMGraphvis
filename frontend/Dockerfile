FROM node:20-alpine

WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the application
COPY . .

# Expose the port the app will run on
EXPOSE 3000

# Command to run the development server
CMD ["npm", "run", "dev"]
