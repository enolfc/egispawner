import uuid
from tornado import gen
from kubespawner import KubeSpawner
from traitlets import List, Bool

class EGISpawner(KubeSpawner):
    custom_images_list = List(
        [],
        config=True,
        help='List of Docker Images users choose in the spawn form.') 

    use_options_form = Bool(
        False,
        config=True,
        help='Setting this to true will enable the default options '
             'form which uses Environment variables to capture which '
             'image specs to use and give resource limits options')

    def _options_form_default(self):
        if self.use_options_form != True:
            return ''
        default_env = "YOURNAME=%s\n" % self.user.name
        image_select = self._load_custom_images_list()
        # TODO(enolfc): this could be largely improve in the rendering
        return """
               <label for="env">Environment variables (one per line)</label><br/>
               <textarea name="env">{env}</textarea><br/>
               {image}
               """.format(env=default_env, image=image_select)

    def _load_custom_images_list(self):
        if self.custom_images_list:
            image_dropdown = [
                '<label for="custom_image">Choose custom image</label><br/>',
                '<select id="custom_image" name="custom_image">',
                '<option value="{}">default</option>'.format(self.singleuser_image_spec)
            ]
            for k, v in self.custom_images_list:
                val = '<option value="{}">{}</option>'.format(k, v)
                image_dropdown.append(val)
            image_dropdown.append('</select><br/>')
            return ''.join(image_dropdown)
        else:
            return ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pvc_name = uuid.uuid4().hex

    def get_pvc_manifest(self):
        pvcs = self.api.list_namespaced_persistent_volume_claim(namespace=self.namespace)
        for pvc in pvcs.items:
            if pvc.metadata.annotations.get('hub.jupyter.org/username', '') == self.user.name:
                self.pvc_name = pvc.metadata.name
                break
        vols = []
        for v in self.volumes:
           if v.get('persistentVolumeClaim', {}).get('claimName'):
               v['persistentVolumeClaim']['claimName'] = self.pvc_name
           vols.append(v)
        self.volumes = vols
        return super().get_pvc_manifest()

    @gen.coroutine
    def get_pod_manifest(self):
        pod = yield super().get_pod_manifest()
        if 'custom_image' in self.user_options:
            notebook_container = pod.spec.containers[0]
            image_spec = self.user_options.get('custom_image')[0]
            notebook_container.image = image_spec
            self.log.info("Will use %s as image spec", notebook_container.image) 
        return pod
