FROM continuumio/miniconda3:latest

# install requirements
COPY conda-environment.yaml conda-environment.yaml
RUN conda env create -f conda-environment.yaml \
    # conda clean up
    && conda clean -afy \
    && find /opt/conda/ -follow -type f -name '*.a' -delete \
    && find /opt/conda/ -follow -type f -name '*.pyc' -delete \
    && find /opt/conda/ -follow -type f -name '*.js.map' -delete

# Copy files
COPY src /var/rk_api
COPY docker/supervisord.conf /opt/conda/envs/riigikantselei/etc/supervisord/conf.d/supervisord.conf
COPY docker/entrypoint.sh /var/rk_api/entrypoint.sh
COPY docker/uwsgi_rk.ini /var/rk_api/uwsgi_rk.ini
COPY docker/nginx.conf /opt/conda/envs/riigikantselei/etc/nginx/sites.d/default-site.conf
COPY docker/create_front_config.py /var/rk_api/create_front_config.py

ENV UWSGI_INI /var/rk_api/uwsgi_rk.ini

COPY VERSION /var/VERSION

# Create  dir for data & logs
RUN mkdir /var/data && mkdir /var/data/logs

WORKDIR /var/rk_api


# Retrieve pre-built front
RUN wget https://packages.texta.ee/riigikantselei-front/riigikantselei-latest.tar.gz \
    && tar -zxvf riigikantselei-latest.tar.gz \
    && cp -r dist/riigikantselei_front/browser /var/rk_api/front \
    && rm riigikantselei-latest.tar.gz && rm -R dist

# Ownership to www-data and entrypoint
RUN chown -R www-data:www-data /var/rk_api \
    && chmod 775 -R /var/rk_api \
    && chmod +x /var/rk_api/entrypoint.sh \
    && rm -rf /root/.cache

# Skip model downloads on build
ENV RK_DOWNLOAD_DATA False
RUN /opt/conda/envs/riigikantselei/bin/python manage.py collectstatic --no-input --clear
ENV RK_DOWNLOAD_DATA True

# Expose ports
EXPOSE 8000
EXPOSE 8001

ENTRYPOINT ["/var/rk_api/entrypoint.sh"]
CMD ["supervisord", "-n"]
