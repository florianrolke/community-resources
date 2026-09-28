FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our wildcard subdomain config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy all site files (redesigns + widget demos)
COPY sites/ /usr/share/nginx/html/sites/

# Copy landing pages (client.of subdomain)
COPY landing/ /usr/share/nginx/html/landing/

# Copy root index (fallback)
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
