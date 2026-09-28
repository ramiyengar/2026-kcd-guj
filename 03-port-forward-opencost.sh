#kubectl port-forward --namespace opencost service/opencost 9003 9090
kubectl port-forward --address 0.0.0.0 --namespace opencost service/opencost 9003:9090
