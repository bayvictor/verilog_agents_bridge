Download 00VerilogCoder.tgz
unzip in your local dir
then "docker-compose up -d "

You will have **6 verilog agents (docker containers of MAGE, NV VerilogCoder, DeepSeek, CodeGen, CodeT5, PolyCoder )**
running in a line-up bridge , mapping them into diff. 6 IP ports. :)
Then you can  run scripts to debug them, test them, 
benmark them, and event see the pub/sub inter-agent pipeline architecture for them!

WARNING: be in special attention: for docker-compose.yaml -- ports mapping to make them working:
<pre>
Version: '3.8'
      - "1883:1883"   # for mqtt, on top inter-agent pipeline
      - "8883:8883"
      - "8081:8080"   # host port 8081 -> container 8080 ## MAGE
      - "8082:8080"   # host port 8081 -> container 8080 ## NV VerilogCoder
      - "8083:8080"   # host port 8081 -> container 8080 ## DeepSeek
      - "8084:8080"   # host port 8081 -> container 8080 ## CodeGen
      - "8085:8080"   # host port 8081 -> container 8080 ## CodeT5
      - "8086:8080"   # host port 8081 -> container 8080 ## PolyCoder

</pre>
