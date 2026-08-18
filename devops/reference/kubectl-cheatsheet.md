# kubectl cheatsheet

## Setup that saves hours

```bash
alias k=kubectl
source <(kubectl completion zsh)
complete -F __start_kubectl k

kubectl config set-context --current --namespace=runproject
```

Install `kube-ps1` or use oh-my-zsh's kubectl plugin so your prompt shows the
current context and namespace. The day you run something destructive against
the wrong cluster is the day you wish you had.

```bash
brew install derailed/k9s/k9s     # terminal UI. genuinely worth it.
```

## The offline documentation

```bash
kubectl explain deployment.spec.template.spec.containers
kubectl explain ingress.spec.rules --recursive
kubectl api-resources
```

**`kubectl explain` is your API reference with no signal.** It reads the
cluster's own OpenAPI schema. Learn to reach for it instead of searching.

## Looking at things

```bash
kubectl get pods                       # -o wide adds node + IP
kubectl get all                        # misses PVCs, Ingresses, Secrets
kubectl get pods -A                    # every namespace
kubectl get pods -w                    # watch
kubectl get pods -l app=backend
kubectl get pods --field-selector status.phase=Running
kubectl get pods --sort-by=.status.startTime
kubectl get deploy,svc,ing,pvc         # multiple kinds at once

kubectl describe pod <name>            # ← Events at the bottom. read them.
kubectl get events --sort-by=.lastTimestamp | tail -30
```

```bash
kubectl get pod <name> -o yaml
kubectl get pod <name> -o jsonpath='{.spec.containers[0].image}'
kubectl get pods -o custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image,NODE:.spec.nodeName
kubectl get pod <name> -o jsonpath='{.status.qosClass}'
```

## Logs

```bash
kubectl logs deploy/backend
kubectl logs deploy/backend -f
kubectl logs <pod> --previous              # ← the CRASHED attempt
kubectl logs -l app=backend --tail=100     # all replicas
kubectl logs deploy/backend --since=1h
kubectl logs deploy/backend -c <container> # multi-container pods
kubectl logs job/migrate-680b5c5
```

`--previous` is the one people forget on a CrashLoopBackOff.

## Getting inside

```bash
kubectl exec -it deploy/backend -- bash
kubectl exec -it deploy/backend -- python manage.py shell
kubectl exec -it db-0 -- psql -U runproject
kubectl exec -it deploy/redis -- redis-cli

kubectl port-forward svc/backend 8000:8000
kubectl port-forward db-0 5432:5432

kubectl cp runproject/backend-xxx:/data/media/f.fit ./f.fit
kubectl cp ./tokens runproject/backend-xxx:/data/garmin_tokens/athlete_1

# ephemeral debug container — for minimal images with no shell
kubectl debug -it <pod> --image=nicolaka/netshoot --target=backend

# the network swiss army knife
kubectl run -it --rm net --image=nicolaka/netshoot --restart=Never -- bash
```

## Applying and deleting

```bash
kubectl apply -f manifest.yaml
kubectl apply -f k8s/
kubectl apply -k k8s/overlays/prod

kubectl diff -f manifest.yaml           # ← what WOULD change. use before apply.
kubectl apply -f x.yaml --dry-run=server

kubectl delete -f manifest.yaml
kubectl delete pod <name> --grace-period=0 --force   # last resort
```

`kubectl diff` before `apply` is a habit worth building.

## Rollouts

```bash
kubectl rollout status deploy/backend --timeout=5m
kubectl rollout history deploy/backend
kubectl rollout history deploy/backend --revision=3
kubectl rollout undo deploy/backend
kubectl rollout undo deploy/backend --to-revision=3
kubectl rollout restart deploy/backend      # no spec change; picks up ConfigMaps
kubectl rollout pause deploy/backend
kubectl rollout resume deploy/backend
```

## Scaling

```bash
kubectl scale deploy/backend --replicas=3
kubectl scale deploy --all --replicas=0        # stop everything
kubectl get hpa
kubectl describe hpa backend
kubectl top pods
kubectl top nodes
```

## Debugging network

```bash
kubectl get endpoints                # ← empty ENDPOINTS explains most 503s
kubectl get endpointslices
kubectl get svc
kubectl describe svc backend
kubectl get ingress
kubectl describe ingress runproject
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller -f
```

## Config, secrets, storage

```bash
kubectl get cm backend-config -o yaml
kubectl get secret backend-secrets -o jsonpath='{.data.DJANGO_SECRET_KEY}' | base64 -d

kubectl create secret generic x --from-literal=a=b --dry-run=client -o yaml
kubectl create cm y --from-env-file=.env --dry-run=client -o yaml

kubectl get pvc,pv
kubectl describe pvc media
kubectl get storageclass
```

## Jobs

```bash
kubectl get jobs,cronjobs
kubectl wait --for=condition=complete job/migrate-680b5c5 --timeout=300s
kubectl create job --from=cronjob/pg-backup manual-1     # test a CronJob now
kubectl delete job migrate-680b5c5
```

## RBAC

```bash
kubectl auth can-i --list
kubectl auth can-i delete secrets -n runproject
kubectl auth can-i --list --as=system:serviceaccount:runproject:ci
```

`auth can-i` is the unit test for your RBAC. Run it after every change.

## Contexts

```bash
kubectl config get-contexts
kubectl config use-context k3s-prod
kubectl config current-context
kubectl config set-context --current --namespace=runproject
```

## Emergency

```bash
kubectl rollout undo deploy/backend
kubectl scale deploy --all --replicas=0 -n runproject
kubectl delete pod -l app=backend                # forces recreation
kubectl cordon <node>                            # no new pods here
kubectl drain <node> --ignore-daemonsets         # move everything off
kubectl uncordon <node>
```

## The five to memorise

```bash
kubectl get pods
kubectl describe pod <name>          # Events section
kubectl logs <name> --previous
kubectl get endpoints                # empty = the answer
kubectl explain <kind>.<path>        # offline docs
```

Those five diagnose the large majority of problems.
