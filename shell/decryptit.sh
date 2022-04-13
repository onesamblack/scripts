#!/bin/bash

while getopts ":k:" arg; do
	case ${arg} in
		k)
			key=${OPTARG}
			;;
		\?)
			echo "unspecified argument -${OPTARG}"
			exit 1
			;;
		:)
			echo "Invalid option: $OPTARG requires an argument" 1>&2
			exit 1
			;;
	esac
done
shift $((OPTIND -1))
if [ !  -f $1 ]
	then
		echo "the file: $1 doesn't exist"
else
	if [ -z $key ]
		then
			echo "need to specify a key using -k"
			exit 1
	fi;
	
	IFS="." read -a prefix  <<< "$1"
	

	if [[ ${prefix[1]} != "enc" ]]
	then
		echo "the filename $1 doesn't end in .enc - you sure brah?"
		exit 1
	fi

	outfile=${prefix[0]}
	echo "decrypting $1 into ${outfile} with ${key}"
	{
		openssl aes-256-cbc -d -in $1 -out "${outfile}" -kfile ${key} -pbkdf2 && \
		rm $1 && \
		echo "decrypted contents" 
	} || { 
		echo "failed to decrypt" 
	} 

fi

