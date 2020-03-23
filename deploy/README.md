# Deployment Instructions for submission-ui

To install submission-ui to the development namespace in the kubernetes cluster:


```bash
helm install ./ --name=submission-ui --set=image.tag=b759ba5 \
  --tiller-namespace=development --namespace=development \
  --set=vault.enabled=1 --set=vault.port=8200 --set=vault.host=<VAULT_HOST_IP> \
  --set=ingress.host=development.arxiv.org --set=ingress.path=/submit
```


This assumes that the requisite Vault roles and policies have already been installed.

To delete the pod, run:
```
helm del --purge submission-ui --tiller-namespace=development
```

Notes:
- `image.tag`: this refers to the tag in [dockerhub](https://hub.docker.com/repository/docker/arxiv/submission-ui)
- `vault.host`: the actual IP of the Vault host can be retrieved from most of the other pods
