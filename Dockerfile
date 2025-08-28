# Usar uma imagem base do Python
FROM python:3.9-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copiar todos os arquivos do projeto para o diretório de trabalho no container
COPY . .

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements

# Expor a porta usada pela aplicação Flask
EXPOSE 80

# Definir a variável de ambiente para o Flask
ENV FLASK_APP=app.py
ENV DB_HOST=mysql
ENV DB_USER=root
ENV DB_PASSWORD=Vms071999
ENV DB_NAME=tonner

# Comando para iniciar a aplicação
CMD ["flask", "run", "--host=0.0.0.0", "--port=80"]
