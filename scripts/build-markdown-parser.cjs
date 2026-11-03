/* Development-only build. Kindle and NAS need no Node dependencies. */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'..');
const deps=path.join(root,'.tools/markdown-build/node_modules');
const babel=require(path.join(deps,'@babel/core'));
const acorn=require(path.join(deps,'acorn'));
async function main(){
 const response=await fetch('https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.js');
 if(!response.ok)throw Error('Parser download failed');
 let source=await response.text();
 if(crypto.createHash('sha256').update(source).digest('hex')!=='433ba2a6946e8200c464d8845b98d826022a1836b4a713f01fa2830477c381e8')throw Error('Source hash changed');
 // The sole Map is a fixed numeric HTML-entity lookup. Scope an ES5 lookup
 // to that one instance instead of modifying the browser's global Map.
 if((source.match(/new Map\(/g)||[]).length!==1)throw Error('Map usage changed');
 source=source.replace('new Map(','new (function(pairs){this.get=function(key){for(var i=0;i<pairs.length;i++){if(pairs[i][0]===key)return pairs[i][1];}};} )(');
 const result=babel.transformSync(source,{presets:[[path.join(deps,'@babel/preset-env'),{targets:{safari:'5.1'},modules:false,useBuiltIns:false}]],comments:false,compact:true}).code;
 acorn.parse(result,{ecmaVersion:5});
 fs.writeFileSync(path.join(root,'kindle-client/extensions/dashboard/app/markdown-it.min.js'),'/* markdown-it 14.1.0, MIT. ES5 build; see MARKDOWN-LICENSE.txt. */\n'+result+'\n');
 console.log('Pinned parser built and checked as ES5.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
