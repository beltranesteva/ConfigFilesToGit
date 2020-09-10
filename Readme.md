# Configuration Files to Git
### Automation aimed to upload configuration files to GitLab ###

 Every time a commit is performed in one of the router's, configuration gets pushed (actually scp-ed) to a particular server. This new file gets detected
  and the script unzips it and uploads it's content to a given repo in GitLab (it tries 3 times. If unable, then error message is logged and an alert send to a
   google chat room). Based on the router's name the file to which it will get uploaded generating a historical log in which changes are easily spotted. 